# Learn Different — Data Science Workstream Report

**GDG AI Hack 2026 · Track: Learn Different (Braynr)**
**Author:** _[your name here]_
**Role:** Data Scientist
**Team:** _[team name here]_
**Date:** May 2026

---

## 0. How to read this document

This is the **technical writeup** for my contribution as data scientist to our team's submission to the *Learn Different* track. It is also the document I am handing to **Claude Code** as the implementation partner for the actual build, alongside the two architectural briefs that accompany it (`INDEXING_AGENT_BRIEF.md` and `EVALUATION_AGENT_BRIEF.md`).

Two audiences, two purposes:

- **For the jury**: this document should make our cognitive-design choices visible and defensible. The track's primary criterion (35% of the score) is whether the team thought deeply about how humans learn, and whether that thinking shows in the system. So this writeup is structured around *decisions*, not features — every section explains *what we chose, what we rejected, and why* in the language of the cognitive frame.
- **For Claude Code**: this document gives the strategic intent. The implementation specs live in the two companion briefs. References to them appear inline. **Do not implement from this document alone** — it is the *why*, not the *how*.

---

## 1. Workstream scope

Three components were assigned to the data-science workstream, each one a LangGraph/LangChain agent:

1. **Onboarding profiling quiz** — characterize the user's study method at session start.
2. **Material indexing agent** — ingest a study artifact (PDF, slides, notes, audio, video) and produce a hierarchical index that the rest of the system can consume.
3. **Response evaluation agent** — evaluate the user's responses to assessments (closed quiz, flashcards, open questions) and drive the learning loop on errors.

Component 2 and 3 form the **core of the demo path** and are fully specified, with implementation briefs ready for Claude Code. Component 1 was explored, then **deliberately deprioritized**, for reasons documented in §3 below.

---

## 2. The cognitive frame — what governs every decision

The track is explicit: the failure mode it punishes is **eduslop**, the production of educational AI that optimizes outputs without producing outcomes. The brief contrasts:

- **Outputs**: the visible artifacts students submit — passed tests, summaries, generated answers.
- **Outcomes**: the intellectual capacities they actually build — genuine understanding, transferable knowledge, analytical reasoning.

The track rewards systems that **support the *process* of learning, not the *answer* at the end**.

This single distinction governed every architectural choice in our workstream. Three corollaries deserve explicit mention:

1. **No score is shown to the student.** Numerical grading collapses cognitively distinct cases into the same number and turns a learning interaction into an evaluation event. This rules out a whole class of designs.
2. **Source-centric traceability is non-negotiable.** Every artifact our system produces — index nodes, assessments, judgments — must trace back to a precise position in the original material. This is what makes "shortcuts structurally useless," in Braynr's framing: the only path through the material is one that requires the user to construct meaning from it.
3. **Process is observable, not just inferable.** Hesitations, self-corrections, reformulations, the specific *kind* of error a student makes — these are signals of what is happening cognitively. A system that ignores them collapses back into output-grading. A system that uses them earns its place under the cognitive frame.

These three corollaries appear, restated and operationalized, in the design of each component below.

---

## 3. Part 1 — Onboarding profiling quiz

### Status: explored, deferred. Not in the demo path.

### What we explored

The original intent was an LLM-driven quiz administered at first session that produces a profile of the user's study method, which downstream agents then use to personalize their behavior.

We surveyed the candidate ground in three directions:

- **Classical "learning styles" instruments** — VARK, Kolb LSI, Honey-Mumford, Felder-Silverman.
- **Self-regulated learning (SRL) and approaches-to-learning instruments** — MSLQ (Pintrich et al., 1991), R-SPQ-2F (Biggs, Kember & Leung, 2001), LASSI, Need for Cognition (Cacioppo & Petty), Grit-S.
- **Behavioral/diagnostic profiling** — observing a small study task rather than asking self-report questions; later refining the profile from the cognitive trace itself.

### What we rejected and why

**The classical "learning styles" hypothesis is largely discredited in the contemporary educational-psychology literature.** Pashler et al. (2008) is the canonical review, and the consensus has only hardened since. VARK-style "you are a visual learner" profiling is one of the named *neuromyths of education*. Building on it would be a direct hit on the "did the team think deeply about how humans learn?" criterion, which is judged at 35%.

This eliminated the most googlable instruments and made clear that *if* a self-report instrument was used, it had to come from the SRL / approaches-to-learning tradition (R-SPQ-2F, MSLQ subscales, Need for Cognition), which has empirical support and is defensible.

### Why we deferred it

Three converging reasons:

1. **The quiz is plumbing.** A self-report instrument is essentially a Likert form whose engineering complexity is low and whose value to the demo lives entirely *downstream* — in how other agents consume the profile. Investing in it before the downstream agents existed risked optimizing a piece nobody else was ready to use.
2. **The cognitive-design budget pointed elsewhere.** Within a 24h window, the highest-leverage cognitive-design move is in components 2 and 3, which are where the cognitive frame actually contacts the user's behavior. A profiling quiz is necessary infrastructure but not where the track is won.
3. **Deferring is reversible; implementing prematurely is not.** A poorly-designed Part 1 leaks bad signal into Parts 2 and 3 and is hard to extract. A missing Part 1 is just a pluggable hole.

### What we would have done

If revived, the design we had converged on was:

- **A self-report instrument of ~20–25 items**, drawn from R-SPQ-2F (Deep / Surface approach to learning, Biggs 2001) and selected MSLQ subscales (metacognitive planning, self-monitoring, help-seeking), plus a short Need for Cognition scale.
- **Output**: a profile vector of 4–6 numerical dimensions that downstream agents can use to vary their behavior. Crucially, *no single "label"* — the profile is a vector, not a category, precisely to avoid the learning-styles trap.
- **An LLM only at the edges**: deterministic Likert scoring, then LLM interpretation to produce a human-readable narrative for the user and a structured input for downstream agents.

### Implication for the demo

We will explain in the live demo that the profile is consumed downstream as an empty/default vector for now, and walk the jury through the design we *would* have used. This is honest, defensible, and makes our cognitive-design reasoning visible without claiming work we did not finish.

---

## 4. Part 2 — Material indexing agent

### Goal

Ingest **any study artifact the user uploads** — PDF (textbook, raw notes, exported slides), PPT/PPTX, Markdown, audio recording, video — and produce a single `index.json` per file: a **hierarchical index** with adaptive depth (chapters → sections → subsections → paragraphs), in which **the leaves are semantic paragraphs** and every node carries a **source locator** for traceability.

> Implementation specification: `INDEXING_AGENT_BRIEF.md`. Refer there for the LangGraph topology, Pydantic models, parser strategies per format, schema, and step-by-step work plan.

### The decisions that matter

#### Decision 1 — Normalized intermediate representation

All format-specific parsers produce the **same** `Document` / `Block` structure, with format-polymorphic `SourceLocator`s (page ranges for PDFs, slide indices for PPTX, char offsets for MD, time ranges for audio/video). After parsing, the rest of the graph is format-agnostic.

**Why this matters cognitively, not just architecturally.** The student does not study "a PDF" or "an audio recording" — they study *content*. The downstream cognitive operations (segmentation, labeling, assessment generation) should not branch on format. By collapsing all formats to a single representation early, we let the cognitive machinery operate on the artifact uniformly. This is a small but real example of the system being designed around the *learner's* abstraction, not the *engineer's*.

#### Decision 2 — Adaptive depth (2 to 4 levels), not forced 4-level hierarchy

A 30-slide deck does not have "chapters." A textbook chapter has subsections. The index produces only the levels the material supports. Forcing a fixed depth would invent fake nodes that propagate noise to downstream agents.

This is a direct application of the *output-vs-outcome* distinction at the structural level: a fixed 4-level hierarchy would be cosmetic structure (output) that does not reflect the material (no outcome). Adaptive depth keeps the index honest.

#### Decision 3 — Leaves are *semantic* paragraphs, not typographic

The leaf node is a **self-contained unit of meaning** — operationally, the smallest unit on which a comprehension question could meaningfully be asked. Not a typographic block, not a fixed-size chunk.

This decision is consequential because it sets the **grain of cognitive operations** for the entire system. Part 3 generates one or more assessments per leaf; the rubric judges responses against one leaf's worth of content; source redirection on errors points back to one leaf. If the leaves are wrong (too small → fragmented; too large → assessment generation overwhelmed; arbitrarily aligned to typography → cognitive misalignment), every downstream cognitive operation degrades.

This is the structural counterpart of Braynr's source-centric thesis: every elaboration must trace back to its origin, **and the origin must be the right size**.

#### Decision 4 — Source preservation rule

The agent **does not summarize, paraphrase, or rewrite**. For textual sources, leaf `text` is verbatim. For audio/video, the transcription is *cleaned* (filler removal, false-start reassembly) but **not summarized or conceptually rephrased**. Internal nodes have only short navigable labels and locators — never a summary body.

This is the most pedagogically important rule in the entire indexing agent. If we allowed the agent to summarize at index time, downstream assessment generation would assess *our summary*, not the *user's actual material* — leaking content into the index and short-circuiting the cognitive elaboration the student is supposed to perform. The student's brain must do the elaboration; we just structure access.

This rule is also what makes traceability work in practice. A summary cannot be located back to a precise position; verbatim text can.

#### Decision 5 — Branching on typographic structure

Two segmentation strategies coexist, and the agent routes between them based on whether the material exhibits reliable structural cues (heading hierarchy in PDFs, slide titles, MD `#`s):

- **Strong structure → build hierarchy from structure.** Faithful reconstruction of the author's intent.
- **Weak/absent structure → semantic segmentation** (LLM-driven for v1) + bottom-up clustering. The "magic" of the agent: structure emerges from a flat blob of text or a transcribed lecture.

This branching is itself a cognitive-design statement: *the index respects the structure the author provided when one exists, and supplies one only when it does not*. The agent does not impose its own structure on a textbook with a perfectly good ToC; it does construct one for raw notes that have none. This restraint is a small but visible respect for the user's material.

### Notable implementation choices (briefly — full detail in the brief)

- **Audio/video**: `faster-whisper` locally (multilingual: IT + EN), `medium` model. Reasoning: a single model covers both languages with one pipeline; the language-specific Italian models we evaluated (FAMA from FBK, distil-whisper-it from bofenghuang) gain a few WER points but at the cost of two pipelines, two models in memory, and a routing layer. The marginal accuracy gain is absorbed by the LLM cleaning step downstream. We accept ~3–5 WER points on Italian to keep the pipeline simple.
- **LLM**: Gemini 2.5 Flash via Google AI Studio (free in our setup), called only for transcript cleaning, semantic segmentation, and node labeling. Each call is constrained by a strict prompt that forbids rewriting/summarization and returns IDs or short labels — never new prose.
- **Out of scope**: cross-file indexing, OCR for scanned PDFs, human-in-the-loop refinement. The agent is a one-shot transcriber-with-structure, not an editor.

---

## 5. Part 3 — Response evaluation agent

### Goal

Evaluate a student's response to an assessment item — closed-form quiz, flashcard, or open question — and **drive the next move in the learning loop**. Critically: not produce a score, but **diagnose the kind of misunderstanding** and **deliver the right scaffolding**.

> Implementation specification: `EVALUATION_AGENT_BRIEF.md`. Refer there for the LangGraph topology, Pydantic models, the rubric and routing tables, the cognitive trace event schema, and the step-by-step work plan.

This is the component that contacts the cognitive frame most directly, and its design was the most heavily weighted exercise in the whole workstream. The decisions below are also the lines of defense in the live demo.

### Decision 1 — Three-dimensional rubric for open questions, binary for closed forms

Open questions are evaluated on **three independent dimensions, each on a 3-level scale**:

- **Completezza** (completeness — `alta` / `parziale` / `assente`): how much of the expected answer is covered.
- **Correttezza** (correctness — `corretta` / `parzialmente_corretta` / `errata`): whether what is stated is factually accurate.
- **Elaborazione** (elaboration — `rielaborata` / `riportata` / `non_valutabile`): whether the student is reformulating in their own words or reporting verbatim.

Closed quiz and flashcards retain a binary `correct/incorrect` evaluation — they are designed to test recall, not to measure elaboration, and forcing them through the 3D rubric would produce noise.

#### Why three dimensions, not one

A monolithic score collapses cognitively distinct cases into the same number. Worked example:

- **Student A**: *"Una catena di Markov è un processo dove il futuro dipende solo dal presente, non dal passato. Quindi è memoryless."*
- **Student B**: *"Una catena di Markov è una sequenza X_1, X_2, ... tale che la probabilità di X_{n+1} dipende solo da X_n."*

A 1-10 scoring system would give both students roughly the same number — both are partial, both are correct. But the cognitive states are opposite: A is reformulating in their own words and missing a piece; B is reciting a textbook definition. They need *opposite* interventions:

- A: fill in the missing piece. *"Ottima intuizione sulla memorylessness, manca però un ingrediente formale — quale?"*
- B: open up the elaboration. *"Vedo che hai la definizione formale. Prova a spiegarmela come la spiegheresti a un compagno — cosa significa che X_{n+1} dipende solo da X_n?"*

The three dimensions make this distinction structurally visible to the routing logic. **Completeness and correctness** capture *what* is said; **elaboration** captures *how* it is said — and "how" is where the *process vs output* distinction becomes operationally measurable.

#### Why elaboration is the cognitive load-bearing dimension

Completeness and correctness are conventional. Plenty of educational tools score them. **Elaboration is the one that anchors the cognitive frame.** It is the dimension that distinguishes a verbatim recitation (output) from a personal reconstruction (outcome). Without it, the rubric is just a finer-grained grading scheme. With it, the rubric becomes a diagnostic instrument.

### Decision 2 — Hide the rubric from the student; expose only the conversational intervention

The rubric, the dimension labels, the routing decisions, the JSON — none of this is shown to the student. The student sees a **conversational intervention** generated from the rubric by an LLM, written in the language of the source material (IT or EN), in the voice of a thoughtful tutor.

**Why.** Exposing the rubric turns a process tool into an evaluation. The student starts gaming dimensions. The point is *not* to issue a report card — it is to drive the right next move. The rubric is the agent's compass, not the student's grade. This is the strongest single point of distance between our system and a typical tutoring chatbot.

### Decision 3 — Routing from rubric to intervention (the "(f) adaptive combination")

The rubric does not stand alone. A **routing logic** maps every rubric pattern to an intervention type:

| Trigger | Intervention |
|---|---|
| Bassa completezza | (b) **diagnostic hint** about what is missing **+** (c) **redirect to source paragraph** — *always combined* |
| Bassa correttezza | (c) **source redirect** primary, optionally (b) a hint pointing at the incorrect element |
| `elaborazione = riportata`, others positive | (d/e) **modality switch** — ask to reformulate, give an example, explain aloud |
| All three positive | Positive feedback, advance |

When multiple dimensions fail simultaneously, intervention priority is **correctness > completeness > elaboration**. Fix the misunderstanding before pushing for elaboration.

#### Why hint + source redirect are *combined* on completeness errors

Either alone is insufficient. A hint without source pushes the student to invent. A source redirect without hint pushes the student to re-read passively. Together they scaffold productive struggle: the hint tells the student *what to think about*; the source redirect provides the *material to think with*.

This is the operationalization of "desirable difficulties" — the productive friction the track brief explicitly cites as the substrate of durable knowledge. It is also the operationalization of source-centricity: every error closes the loop by sending the student back to the original paragraph, which is the gravitational center of Braynr's whole pedagogical thesis.

### Decision 4 — Two-strikes rule

Every assessment grants **one retry**. After the second wrong attempt on the same `node_id`, the agent unconditionally falls back to **full source redirect** with a longer excerpt and an explicit pointer ("rilegga questa sezione prima di continuare"). The concept is then marked `fragile` in the cognitive trace.

**Why.** Forcing a third attempt without source access is not productive struggle — it is frustration, and frustration produces avoidance, not learning. The rule encodes a pedagogical principle that scaffolding has limits, and at that limit the right move is to send the student back to the original material. The `fragile` flag also creates a hook for downstream spaced repetition or upstream profile updates: a moment of difficulty becomes a cognitive trace that informs *future* sessions.

### Decision 5 — Audio responses and the paralinguistic signal

For open questions, the student can answer **either by typing or by recording audio**.

- **Level 1 — transcription (always)**. Whisper transcribes the audio. The transcript becomes the textual input to the rubric.
- **Level 2 — paralinguistic feature extraction (the cognitive innovation)**. We extract from the Whisper output:
  - **Hesitations** ("aspetta no…", "ehm…"): signals of live meaning construction.
  - **Self-corrections** ("dipende dal passato — no scusa, dal presente!"): signals of active self-monitoring (metacognition).
  - **Reformulations** (saying the same idea two or three different ways): signals of trying to make it click.
  - **Pause statistics** (filler density, inter-segment pauses): signals of cognitive load.

These features are **passed into the rubric judge** with explicit instructions on how to weight them. They primarily affect the `elaborazione` dimension.

#### Why this matters

A textbook-perfect answer typed verbatim is `riportata`. The same answer spoken with hesitations and self-corrections is `rielaborata`. **The cognitive frame says "process, not output," and process is literally audible in ways it isn't visible in text.** Hesitations, self-corrections, and reformulations are the externalization of metacognition. Text alone misses them.

This is the single feature in our system where audio input does something text cannot. It is the kind of "non-obvious interpretation of the cognitive frame" the track explicitly rewards under Innovation in Frame Adherence (30% of the score).

### Decision 6 — Cognitive trace as event-per-turn, not session summary

The agent emits **one structured JSON event per turn** (rubric output, intervention chosen, student message, paralinguistic features, concept status), aligned with Braynr's existing JSON cognitive trace format. There is no separate session summary file: the events *are* the source of truth, and any summary view is computed from them at read time.

This matches Braynr's architectural prior ("a structured event log captures user actions and their temporal sequence") and creates a clean substrate for downstream consumers — whether that is a study analytics dashboard, a spaced-repetition scheduler, or a refinement signal back to the upstream profile from Part 1.

---

## 6. How the three parts interlock

```
   ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
   │  Part 1 (deferred)│        │   Part 2          │        │   Part 3          │
   │  Profiling quiz   │   ──►  │   Indexing agent  │   ──►  │   Eval agent      │
   │  (vector profile) │        │   (index.json)    │        │   (TraceEvents)   │
   └──────────────────┘        └──────────────────┘        └──────────────────┘
              │                          │                          │
              │                          │                          │
              └──────────────► personalize judge prompts ◄──────────┘
                                         │
                                         ▼
                                Braynr (downstream)
                                source-centric workflows
```

The contract:

- **Part 1 → Part 3**: the profile vector personalizes the rubric judge's interpretation (e.g., a student profiled as "deep approach" is evaluated more strictly on `elaborazione`). For the demo, this slot is wired but receives a default vector.
- **Part 2 → Part 3**: every assessment item carries a `node_id` from the Part 2 index. Without this link, **source redirection cannot work** — and source redirection is what closes every error loop in Part 3. This is the single hardest contract in the system, and it is fully specified in both implementation briefs.
- **Part 3 → downstream**: TraceEvents go to Braynr's cognitive trace store. Other agents (spaced repetition, analytics, future Part 1 refinement) consume them.

---

## 7. What we explicitly did not build, and why

A short list, because it matters for honest evaluation:

- **Cross-file knowledge integration** in Part 2. One file → one index. Cross-file alignment is a doctoral-thesis problem in 24 hours; we picked the version with a defensible scope.
- **Human-in-the-loop refinement** in Part 2. The agent emits a final index, no draft-and-correct cycle. This is partly a time choice and partly a cognitive-design choice: we did not want the agent to become a co-author of the structure; we wanted the structure to come from the material.
- **OCR for scanned PDFs**. Out of scope. Scanned PDFs fail loudly with an explicit error. We considered this preferable to silently producing garbage.
- **Score-display to the student**, anywhere in the system. Not a feature we considered cutting late; a feature we ruled out by principle in the cognitive frame.
- **A "show the correct answer" path** in Part 3. Even on the second strike, we redirect to the source — never reveal. This is the strongest commitment to Braynr's source-centric thesis we could make.

---

## 8. What I want from Claude Code

This section is for Claude Code specifically. Three asks, in order:

### Ask 1 — Read the briefs first, then this report

The companion documents are:

- `INDEXING_AGENT_BRIEF.md` — full architectural specification for Part 2, including LangGraph topology, Pydantic models, parser strategies, output schema, and a six-phase work plan with exit criteria.
- `EVALUATION_AGENT_BRIEF.md` — full architectural specification for Part 3, including the rubric, the routing table, the cognitive trace event schema, the paralinguistic feature extraction strategy, the LLM configuration with `--pro` flag, and a six-phase work plan with exit criteria.

This report is the **why**; the briefs are the **how**. Read the briefs first; come back here when you need to understand the cognitive rationale behind a specific choice.

### Ask 2 — Discuss the open questions before coding

Both briefs end with a list of open tactical questions (library choices among equivalents, exact prompt wording, heuristic-vs-LLM choices, error handling policies). Before writing implementation code, walk through those open questions with me. The strategic direction is fixed; the tactical choices are not, and I want to be involved in them.

The most prompt-sensitive node in the entire system is `judge_open` in Part 3. **Iterate on at least 6 hand-crafted fixture cases before considering its prompt finalized.** The `elaborazione` dimension in particular is where LLM judges drift toward giving credit for verbose answers; the prompt must specifically counter that.

### Ask 3 — Honor the cognitive-design constraints

Three constraints are non-negotiable, regardless of implementation convenience:

1. **No score is shown to the student.** No numerical grade, no dimension labels, no JSON, no rubric machinery exposed in any user-facing surface.
2. **The agent never reveals the correct answer.** Even on the second strike, redirect to source.
3. **The source-preservation rule in Part 2 is absolute.** No summarization, no paraphrasing, no rewriting of source content — only structuring access to it.

If during implementation any of these constraints feels like it conflicts with a tactical need, **flag it and we discuss**. Do not relax them silently.

### Ask 4 — Where to spend time, where to cut

Both briefs include explicit "cuts under time pressure" sections. The non-negotiables for the demo path are:

- **Part 2**: PDF (structured) parser end-to-end, plus audio (faster-whisper) end-to-end. These two cover the full visual range of the demo.
- **Part 3**: open-question rubric judge with text input. This is the cognitive payload of the whole submission.

Everything else is welcome but cuttable.

---

## 9. Cognitive-design summary (jury-facing)

If a juror asks me to compress the cognitive design of our workstream into one minute, the answer is:

> *We treated every component as a chance to instrument the **process** of learning, not the artifact at the end of it.*
>
> *The indexing agent preserves source content verbatim and traces every node back to its origin, so downstream agents cannot leak shortcuts into the system. The leaves are semantic units, not typographic blocks, so cognitive operations operate on the right grain. Structure is adaptive to the material, not imposed on it.*
>
> *The evaluation agent diagnoses **what kind** of misunderstanding the student has — not whether they passed — using a three-dimensional rubric where the third dimension, **elaborazione**, distinguishes parroting from understanding. The diagnosis routes to a scaffolding intervention: a hint paired with a source redirect, or a modality switch that asks the student to reformulate. The rubric is **never shown to the student** — it is the agent's compass, not the student's grade.*
>
> *Audio input is not just transcription: hesitations, self-corrections, and reformulations are the externalization of metacognition, and we feed them into the rubric judge. A textbook-perfect answer typed verbatim is **riportata**; the same answer spoken with productive friction is **rielaborata**. The cognitive frame is "process, not output," and process is **literally audible** in ways it isn't visible in text.*
>
> *We deferred the profiling quiz in Part 1 because the cognitive-design budget pointed at the components that make direct contact with the user's behavior. We chose to build less and build it honestly.*

---

## 10. References to the implementation specs

- `INDEXING_AGENT_BRIEF.md` — Part 2 specification, six-phase work plan, open tactical questions.
- `EVALUATION_AGENT_BRIEF.md` — Part 3 specification, six-phase work plan, open tactical questions.

These are the documents Claude Code follows. This report is the reasoning that produced them.

---

_End of report._
