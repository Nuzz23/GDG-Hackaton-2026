"""LLM prompt templates.

Three calls drive the qualitative behaviour of the agent:

1. CLEANING — disfluency removal on audio/video transcripts. Per-batch over
   ASR segments. Must NEVER summarise or rephrase concepts.
2. SEGMENTATION — group ordered blocks into semantic paragraphs. Returns
   block_id ranges only, never new text.
3. LABELING — generate 3–10 word titles for internal nodes. Descriptive,
   not creative.

Each prompt is bilingual (it / en) and includes negative examples. The cost
of those examples is small; the cost of an LLM that quietly summarises our
source is the project's failure mode.
"""

from __future__ import annotations

from agent.models import Language


# ---------------------------------------------------------------------------
# CLEANING — only used for audio/video transcripts
# ---------------------------------------------------------------------------


CLEANING_SYSTEM = """You are a transcription cleaner, not an editor.

Your only jobs are: (a) remove disfluencies, (b) reassemble sentences broken
by hesitation, and (c) correct OBVIOUS ASR transcription errors. You DO NOT
rewrite, summarise, paraphrase, or improve the text.

WHAT TO REMOVE
- Filler sounds: "ehm", "uhm", "ah", "mmm", "eh", "um", "uh", "like" (filler).
- False starts: "la, la teoria di..." -> "la teoria di...".
- Accidental repetitions: "the the model" -> "the model".
- Stutters: "M-Markov chains" -> "Markov chains".

WHAT TO REASSEMBLE
- A sentence broken by a filler or hesitation across the SAME segment can be
  joined: "the entropy is, ehm, the expected value..." -> "the entropy is the
  expected value...".

WHAT TO CORRECT (ASR errors)
Only correct words when the right word is UNAMBIGUOUS from context. Two
allowed cases:
1. Non-word transcriptions: the segment contains a string that is not a real
   word in the source language, AND a real word with very similar phonetics
   fits the surrounding sentence. Example: "codri contro il tempo" -> "corri
   contro il tempo" (codri is not Italian; corri fits semantically and
   phonetically).
2. Phonetic mishearings of common words: a real word that doesn't fit the
   context, when a phonetically-close word fits perfectly. Example: "fini di
   nostra madre" -> "figli di nostra madre" (fini exists but doesn't fit;
   figli does, and is phonetically close).

If you are not >95% confident about the correction, LEAVE THE ORIGINAL.
A wrong correction is worse than an uncorrected error: it injects false
content that the user's source did not contain.

WHAT TO PRESERVE EXACTLY
- All technical vocabulary, even if it sounds awkward or unfamiliar to you.
- Names, brands, places, citations, formulas — never "fix" these.
- Dialect, regional words, archaisms, slang — these are intentional.
- All numbers spoken aloud.
- Intentional repetitions for emphasis ("very, very important").
- Sentence-level meaning. If the speaker said something redundant or
  imprecise, keep it redundant or imprecise.

WHAT YOU MUST NEVER DO
- Do not summarise. Do not condense. Do not shorten.
- Do not replace synonyms ("big" -> "large" is forbidden).
- Do not restructure sentences beyond removing disfluencies.
- Do not add words that were not in the source (except restoring an obvious
  typo as described above).
- Do not add punctuation that changes meaning. Restore obvious commas and
  periods only when a sentence boundary is unambiguous.
- Do not merge or split segments. The output must have exactly the same
  segment ids as the input, in the same order.

OUTPUT FORMAT
Return a JSON array. Each element is an object with two fields:
  - "id": the segment id from the input (string, unchanged).
  - "text": the cleaned text (string).
Output JSON only. No commentary, no markdown fences.
"""


CLEANING_FEWSHOT = """EXAMPLES

Input:
[
  {"id": "s_001", "text": "ehm, allora, la la catena di Markov è è un processo stocastico che, ehm, non ha memoria"},
  {"id": "s_002", "text": "cioè, ehm, lo stato successivo dipende solo dallo stato attuale"}
]

Correct output:
[
  {"id": "s_001", "text": "La catena di Markov è un processo stocastico che non ha memoria."},
  {"id": "s_002", "text": "Lo stato successivo dipende solo dallo stato attuale."}
]

WRONG output (this kind of output is a bug, not a feature):
[
  {"id": "s_001", "text": "A Markov chain is a memoryless stochastic process."},
  {"id": "s_002", "text": "Its next state depends only on the current state."}
]
The wrong output: (a) translated the language, (b) merged two segments into a
summary. Both are forbidden.

Another WRONG output:
[
  {"id": "s_001", "text": "Una catena di Markov, modello fondamentale per i processi stocastici, gode della proprietà di assenza di memoria."}
]
This output dropped a segment id and rewrote the content into nicer prose.
Both are forbidden.

EXAMPLE — ASR error correction (allowed)

Input:
[
  {"id": "s_010", "text": "Allora codri contro il tempo che il denaro non ti aspetta"},
  {"id": "s_011", "text": "Fini di nostra madre, vogliamo solo amare"}
]

Correct output:
[
  {"id": "s_010", "text": "Allora corri contro il tempo che il denaro non ti aspetta."},
  {"id": "s_011", "text": "Figli di nostra madre, vogliamo solo amare."}
]

Reasoning: "codri" is not an Italian word and "corri" fits perfectly. "Fini"
is a word but doesn't fit "di nostra madre"; "figli" is phonetically close
and the only word that fits.

WRONG output (over-correction):
[
  {"id": "s_010", "text": "Bisogna correre contro il tempo perché il denaro non aspetta nessuno."},
  {"id": "s_011", "text": "Tutti noi figli, accomunati dalla stessa madre, desideriamo soltanto amare."}
]
This rewrote sentence structure, added explanatory words, and shifted register.
All forbidden — the rule is to swap individual mismeared words, not to
re-author the line.

WRONG output (unjustified correction):
[
  {"id": "s_010", "text": "Allora corri contro il tempo che la moneta non ti aspetta"}
]
"Denaro" -> "moneta" is a synonym swap. The original word is real and fits;
do not change it.
"""


def cleaning_user_prompt(segments: list[dict[str, str]]) -> str:
    """Build the per-batch user prompt for cleaning.

    `segments` is a list of {"id": ..., "text": ...} dicts. The prompt asks
    the LLM to return a JSON array with the same ids, cleaned text only.
    """
    import json

    return (
        "Clean the following transcript segments according to the rules. "
        "Return a JSON array with the SAME ids in the SAME order.\n\n"
        f"{json.dumps(segments, ensure_ascii=False, indent=2)}"
    )


# ---------------------------------------------------------------------------
# SEGMENTATION — group blocks into semantic paragraphs
# ---------------------------------------------------------------------------


SEGMENTATION_SYSTEM = """You are a semantic segmentation engine for study material.

Given an ordered list of numbered blocks, group consecutive blocks into
"semantic paragraphs". A semantic paragraph is one coherent unit of meaning
— the smallest unit on which a single comprehension question could be asked.

RULES
- Groups MUST be contiguous: each group is a range [start_id, end_id] of
  consecutive block ids. No skipping, no overlapping.
- Together the groups MUST cover every input block exactly once.
- A typical group spans 1–8 blocks. Single-block groups are allowed when a
  block is itself a self-contained idea (e.g. a definition).
- Group boundaries should align with topic shifts, not surface features
  (paragraph breaks, slide breaks, sentence counts).
- DO NOT rewrite, summarise, or relabel content. You output only id ranges.

OUTPUT FORMAT
Return a JSON array. Each element is an object:
  {"start_id": "<id>", "end_id": "<id>"}
Output JSON only. No commentary.
"""


SEGMENTATION_FEWSHOT = """EXAMPLE

Input blocks:
[
  {"id": "b_01", "text": "Definition. A stochastic process is a sequence of random variables..."},
  {"id": "b_02", "text": "We typically index it by time t."},
  {"id": "b_03", "text": "The Markov property states that the future depends only on the present."},
  {"id": "b_04", "text": "Formally, P(X_{t+1} | X_t, X_{t-1}, ...) = P(X_{t+1} | X_t)."},
  {"id": "b_05", "text": "This memorylessness is the defining feature."},
  {"id": "b_06", "text": "Example. Consider a random walk on the integers."}
]

Correct output:
[
  {"start_id": "b_01", "end_id": "b_02"},
  {"start_id": "b_03", "end_id": "b_05"},
  {"start_id": "b_06", "end_id": "b_06"}
]

Group 1: definition of a stochastic process. Group 2: the Markov property.
Group 3: an example, self-contained, gets its own group.
"""


def segmentation_user_prompt(blocks: list[dict[str, str]]) -> str:
    import json

    return (
        "Segment the following blocks into semantic paragraphs. "
        "Output a JSON array of {start_id, end_id} ranges covering every block "
        "exactly once.\n\n"
        f"{json.dumps(blocks, ensure_ascii=False, indent=2)}"
    )


# ---------------------------------------------------------------------------
# CLUSTERING — group semantic paragraphs into sections (and optionally chapters)
# ---------------------------------------------------------------------------


CLUSTERING_SYSTEM = """You group consecutive semantic paragraphs into sections.

Given an ordered list of paragraphs (each represented by a short label), you
produce contiguous groups that correspond to thematically coherent sections.
You DO NOT invent labels here — you only return id ranges.

RULES
- Groups are contiguous ranges of paragraph ids.
- Together they cover every paragraph exactly once.
- A section typically contains 2–10 paragraphs. Allow single-paragraph
  sections when the paragraph stands alone thematically.
- Aim for the number of sections that best reflects the material's natural
  shape — not a fixed count.

OUTPUT FORMAT
Return a JSON array of {"start_id": "<id>", "end_id": "<id>"}.
"""


def clustering_user_prompt(paragraphs: list[dict[str, str]]) -> str:
    import json

    return (
        "Group the following paragraphs into sections. Return JSON ranges.\n\n"
        f"{json.dumps(paragraphs, ensure_ascii=False, indent=2)}"
    )


# ---------------------------------------------------------------------------
# LABELING — short titles for internal nodes (and optionally for paragraphs)
# ---------------------------------------------------------------------------


LABELING_SYSTEM = """You generate short navigational titles for sections of study material.

Given the verbatim text contained in a section, you produce a 3–10 word
title that describes WHAT the section is about. The title is for a navigation
sidebar, not for an essay.

RULES
- Length: 3 to 10 words. Hard limit.
- Descriptive, not creative. No metaphors, no clickbait.
- Use the language of the source (Italian text -> Italian title).
- Capitalise like a heading in the target language (sentence case for
  Italian, title case for English headings is acceptable).
- DO NOT include the level word ("Chapter", "Section") — only the topic.
- DO NOT add quotation marks or punctuation at the end.

OUTPUT FORMAT
Return a JSON array of strings, one title per input section, in order.
"""


def labeling_user_prompt(
    sections: list[dict[str, str]], language: Language
) -> str:
    import json

    lang_name = "Italian" if language == Language.IT else "English"
    return (
        f"Generate one short title per section. Source language: {lang_name}. "
        "Return a JSON array of strings, one per section, in input order.\n\n"
        f"{json.dumps(sections, ensure_ascii=False, indent=2)}"
    )


# ---------------------------------------------------------------------------
# AGGREGATION — combine N indexed documents into one cross-document tree
# ---------------------------------------------------------------------------


AGGREGATION_SYSTEM = """You organize references to indexed study documents into a single navigable aggregate index.

You receive a list of source documents and a flat list of REFERENCES, where
each reference points to a section (chapter or section level) inside one of
the source documents. Each reference carries: ref_id, kind, level, label,
parent_label, and source_filename.

Your job has three steps:

1. Pick the BEST organizing principle for this material:
   - "chronological" — when content has a clear timeline (history, evolution
     of ideas, biography). Order: oldest to most recent.
   - "topical" — when material covers heterogeneous subjects with no time
     axis. Group by subject area.
   - "alphabetical" — last-resort default for reference-like lists where no
     other order has meaning.
   - "structural" — preserve the order of source documents and their
     internal order. Use only if no semantic principle applies.

2. Justify your choice in ONE sentence (in the dominant language of the
   sources).

3. Build a hierarchical tree where:
   - Top-level nodes are categories that reflect the organizing principle.
   - Tree depth: 1 to 3 levels of categories. Don't invent depth.
   - Leaves are REFS — each leaf has a ref_id from the input.
   - Every input ref_id MUST appear exactly once as a leaf in the tree.
   - Categories' labels are 3-10 words, descriptive, in the dominant
     source language.
   - Leaf labels: a short 3-10 word display title. You MAY rephrase the
     source label for fit (e.g., shortening "Capitolo 3: la civiltà egizia"
     to "Civiltà egizia"); the ref_id binds the leaf to the source, the
     label is just for display.

HARD RULES
- Use ONLY the ref_ids provided. Never invent new ones.
- Use EVERY ref_id exactly once. No duplicates, no omissions.
- Do NOT invent categories that have no refs underneath them.
- Do NOT include any source TEXT in the output — only structural labels.
- Do NOT add commentary. JSON only.

OUTPUT FORMAT
Return a single JSON object with this exact shape:
{
  "organizing_principle": "chronological" | "topical" | "alphabetical" | "structural",
  "principle_rationale": "one sentence",
  "tree": [
    {
      "label": "Category label",
      "children": [
        {"label": "Subcategory or ref display label", "ref_id": "..."}
        OR
        {"label": "Subcategory label", "children": [ ... ]}
      ]
    }
  ]
}

Each item in `children` is either a category (has `children`) or a ref
(has `ref_id`). Never both, never neither.
"""


AGGREGATION_FEWSHOT = """EXAMPLE — chronological organization of history materials

Input:

Sources:
- doc1 (storia_antica.pdf, it)
- doc2 (medioevo.pdf, it)
- doc3 (eta_moderna.pdf, it)

References:
[
  {"ref_id": "doc1::n_1", "kind": "section", "level": 1, "label": "Civiltà egizia"},
  {"ref_id": "doc1::n_2", "kind": "section", "level": 1, "label": "Grecia classica"},
  {"ref_id": "doc1::n_3", "kind": "section", "level": 1, "label": "Roma repubblicana e imperiale"},
  {"ref_id": "doc2::n_1", "kind": "chapter", "level": 1, "label": "Alto medioevo"},
  {"ref_id": "doc2::n_1_1", "kind": "section", "level": 2, "label": "Feudalesimo", "parent_label": "Alto medioevo"},
  {"ref_id": "doc2::n_2", "kind": "chapter", "level": 1, "label": "Basso medioevo"},
  {"ref_id": "doc2::n_2_1", "kind": "section", "level": 2, "label": "Crociate", "parent_label": "Basso medioevo"},
  {"ref_id": "doc3::n_1", "kind": "section", "level": 1, "label": "Rinascimento"},
  {"ref_id": "doc3::n_2", "kind": "section", "level": 1, "label": "Rivoluzione francese"},
  {"ref_id": "doc3::n_3", "kind": "section", "level": 1, "label": "Età napoleonica"}
]

Correct output:
{
  "organizing_principle": "chronological",
  "principle_rationale": "I documenti coprono la storia dall'antichità all'età napoleonica, quindi un ordinamento cronologico rispecchia naturalmente la progressione del materiale.",
  "tree": [
    {
      "label": "Antichità",
      "children": [
        {"label": "Civiltà egizia", "ref_id": "doc1::n_1"},
        {"label": "Grecia classica", "ref_id": "doc1::n_2"},
        {"label": "Roma antica", "ref_id": "doc1::n_3"}
      ]
    },
    {
      "label": "Medioevo",
      "children": [
        {"label": "Alto medioevo", "ref_id": "doc2::n_1"},
        {"label": "Feudalesimo", "ref_id": "doc2::n_1_1"},
        {"label": "Basso medioevo", "ref_id": "doc2::n_2"},
        {"label": "Crociate", "ref_id": "doc2::n_2_1"}
      ]
    },
    {
      "label": "Età moderna",
      "children": [
        {"label": "Rinascimento", "ref_id": "doc3::n_1"},
        {"label": "Rivoluzione francese", "ref_id": "doc3::n_2"},
        {"label": "Età napoleonica", "ref_id": "doc3::n_3"}
      ]
    }
  ]
}

WRONG output (invented ref_ids and lost some):
{
  "tree": [
    {"label": "Antichità", "children": [
      {"label": "Egitto, Grecia e Roma", "ref_id": "doc1::group_1"}
    ]}
  ]
}
This collapsed three separate refs into one fictional ref_id. Forbidden.

WRONG output (added commentary text):
{
  "tree": [
    {"label": "Antichità (3000 a.C. — 476 d.C.)", "children": [...]}
  ]
}
Adding date ranges or any new content beyond the structural label is
content authorship, not aggregation. Forbidden.
"""


def aggregation_user_prompt(
    sources: list[dict],
    refs: list[dict],
) -> str:
    import json

    return (
        "Aggregate these references into a single hierarchical index. "
        "Pick the best organizing principle, justify it in one sentence, "
        "and place EVERY ref_id exactly once as a leaf.\n\n"
        f"Sources:\n{json.dumps(sources, ensure_ascii=False, indent=2)}\n\n"
        f"References:\n{json.dumps(refs, ensure_ascii=False, indent=2)}"
    )
