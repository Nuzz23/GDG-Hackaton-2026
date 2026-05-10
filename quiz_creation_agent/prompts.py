"""LLM prompts for assessment generation.

Three item types, three prompt families. Every prompt enforces three rules:

1. Source-grounded only — never introduce facts not in the supplied text.
   The Part 3 brief is explicit: assessment must observe the user's grasp
   of THE source, not the model's general knowledge.
2. Difficulty calibrated — facile/medio/difficile follow Bloom-style tiers.
3. Strict JSON output — no commentary, no markdown fences.

Each prompt has a few-shot block with at least one negative example showing
the kind of failure the prompt is hardened against.
"""

from __future__ import annotations

from quiz_creation_agent.models import Difficulty


_DIFFICULTY_DESCRIPTIONS = {
    Difficulty.FACILE: (
        "Pure recall. Test that the user remembers a definition, a single "
        "stated fact, a name, a date, a formula stated in the source. "
        "Answers should be obvious if the user has read the passage attentively."
    ),
    Difficulty.MEDIO: (
        "Comprehension. Test that the user understands a relation stated in "
        "the source — a cause and its effect, a concept and its example, a "
        "claim and its justification. Answers require connecting two parts "
        "of the passage, not just quoting one line."
    ),
    Difficulty.DIFFICILE: (
        "Synthesis or application. Test that the user can combine multiple "
        "ideas from the source, apply a concept to a new instance discussed "
        "in the source, or compare/contrast two ideas the source presents. "
        "All grounded in the source — never extrapolate beyond it."
    ),
}


# ---------------------------------------------------------------------------
# Common scaffolding
# ---------------------------------------------------------------------------


_GROUNDING_RULES = """GROUNDING RULES (apply to every item type)

- Use ONLY information present in the source text. Never introduce facts,
  examples, dates, or relationships that are not stated in the source.
- If the source does not contain enough material to produce N high-quality
  items at the requested difficulty, produce fewer items rather than padding
  with low-quality ones. The output array can be shorter than requested.
- Use the source's language for the items (Italian source -> Italian
  questions and answers, etc.).
- Do not include the answer inside the question stem (no leakage).
- Vary the items: different concepts, different sentence patterns. Avoid
  asking 5 versions of the same question.
"""


# ---------------------------------------------------------------------------
# FLASHCARD
# ---------------------------------------------------------------------------


FLASHCARD_SYSTEM = f"""You generate flashcards for spaced-repetition study from a passage of study material.

Each flashcard is a tight prompt-answer pair where:
- FRONT is a single self-contained cue: a question, a definition prompt, a
  fill-in-the-blank, or a "What is X?" form.
- BACK is the answer, drawn directly from the source. Concise (1-3 sentences
  for medium/hard, a single phrase for easy recall).

ONE concept per card. Cards should be answerable without seeing the source.

{_GROUNDING_RULES}

OUTPUT FORMAT
A JSON array of objects: [{{"front": "...", "back": "..."}}, ...].
JSON only. No commentary, no markdown fences.
"""


FLASHCARD_FEWSHOT = """EXAMPLE — facile

Source (excerpt):
"La proprietà di Markov afferma che lo stato successivo di un processo
stocastico dipende solo dallo stato corrente, non dalla storia passata.
Questo è equivalente a dire che il processo è 'senza memoria'."

Correct output:
[
  {"front": "Cosa afferma la proprietà di Markov?", "back": "Che lo stato successivo di un processo stocastico dipende solo dallo stato corrente, non dalla storia passata."},
  {"front": "Quale aggettivo descrive un processo che gode della proprietà di Markov?", "back": "Senza memoria."}
]

WRONG output (introduces a fact not in the source):
[
  {"front": "Chi ha formulato la proprietà di Markov?", "back": "Andrey Markov nel 1906."}
]
The source does not say who or when. Forbidden — that's the model's outside
knowledge, not assessment of the source.

WRONG output (answer leaks into question):
[
  {"front": "La proprietà di Markov afferma che lo stato successivo dipende solo dallo stato corrente, non dalla storia passata. Vero o falso?", "back": "Vero."}
]
The question contains the answer verbatim. Forbidden.
"""


def flashcard_user_prompt(text: str, n: int, difficulty: Difficulty, language: str) -> str:
    return (
        f"Generate up to {n} flashcards from the following source.\n"
        f"Difficulty: {difficulty.value} — {_DIFFICULTY_DESCRIPTIONS[difficulty]}\n"
        f"Source language: {language}.\n\n"
        f"--- SOURCE TEXT ---\n{text}\n--- END SOURCE ---"
    )


# ---------------------------------------------------------------------------
# MULTIPLE-CHOICE QUESTION
# ---------------------------------------------------------------------------


MCQ_SYSTEM = f"""You generate multiple-choice assessment items from a passage of study material.

Each MCQ has:
- a STEM that asks one clear question
- exactly 4 OPTIONS
- exactly ONE correct option (correct_index in 0..3)
- 3 plausible DISTRACTORS (wrong but defensible mistakes a half-prepared
  student might make), not obvious throwaways
- a brief EXPLANATION of why the correct answer is right, drawn from the
  source. The eval agent will use this for feedback.

DESIGN RULES (in addition to the grounding rules)
- Distractors test understanding, not gotcha-ism. Avoid trick wording.
- The correct answer should not be the longest option (a known giveaway).
- No "all of the above" / "none of the above".
- All four options should be of comparable length and grammatical form.
- Vary correct_index across items (don't always put the answer at index 0).

{_GROUNDING_RULES}

OUTPUT FORMAT
A JSON array of objects:
[{{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 2, "explanation": "..."}}, ...]
JSON only. No commentary, no markdown fences.
"""


MCQ_FEWSHOT = """EXAMPLE — medio

Source (excerpt):
"Il teorema di Bayes esprime la probabilità a posteriori P(A|B) come il
prodotto della verosimiglianza P(B|A) e della probabilità a priori P(A),
diviso la probabilità marginale P(B). È utile quando si conosce la
verosimiglianza ma si vuole stimare la probabilità di una causa dato un
effetto osservato."

Correct output:
[
  {
    "question": "Secondo il teorema di Bayes, come si calcola P(A|B)?",
    "options": [
      "P(A|B) = P(B|A) + P(A) - P(B)",
      "P(A|B) = P(B|A) · P(A) / P(B)",
      "P(A|B) = P(A) · P(B) / P(B|A)",
      "P(A|B) = 1 - P(B|A)"
    ],
    "correct_index": 1,
    "explanation": "Il testo afferma che P(A|B) è il prodotto della verosimiglianza P(B|A) e della probabilità a priori P(A), diviso la probabilità marginale P(B)."
  }
]

WRONG output (correct answer is conspicuously longer than distractors):
[
  {
    "question": "Quando è utile il teorema di Bayes?",
    "options": [
      "Mai",
      "Sempre",
      "Solo per dati continui",
      "Quando si conosce la verosimiglianza ma si vuole stimare la probabilità di una causa dato un effetto osservato"
    ],
    "correct_index": 3,
    "explanation": "..."
  }
]
The correct option is dramatically longer. Length-as-tell — forbidden.
"""


def mcq_user_prompt(text: str, n: int, difficulty: Difficulty, language: str) -> str:
    return (
        f"Generate up to {n} multiple-choice questions from the following source.\n"
        f"Difficulty: {difficulty.value} — {_DIFFICULTY_DESCRIPTIONS[difficulty]}\n"
        f"Source language: {language}.\n\n"
        f"--- SOURCE TEXT ---\n{text}\n--- END SOURCE ---"
    )


# ---------------------------------------------------------------------------
# OPEN QUESTION
# ---------------------------------------------------------------------------


OPENQ_SYSTEM = f"""You generate open-ended comprehension questions from a passage of study material.

Each item has:
- QUESTION: a clear question the user can answer in 1-3 sentences. Avoid
  yes/no questions and avoid questions that have a single keyword answer.
  The user must articulate their understanding.
- EXPECTED_ANSWER: a 1-3 sentence outline of a good answer, drawn strictly
  from the source. This is what the eval agent will compare against.
- KEY_POINTS: 3-5 short phrases naming the specific points a complete
  answer should touch on. The eval agent will check coverage.

{_GROUNDING_RULES}

OUTPUT FORMAT
A JSON array of objects:
[{{"question": "...", "expected_answer": "...", "key_points": ["...", "..."]}}, ...]
JSON only. No commentary, no markdown fences.
"""


OPENQ_FEWSHOT = """EXAMPLE — difficile

Source (excerpt):
"Il principio di separazione degli accessi distingue tra agenti che leggono
contenuti non fidati e agenti che hanno accesso in scrittura ai sistemi.
Il reader può consultare documenti esterni ma non ha accesso a strumenti
MCP né può scrivere file. Il resolver, viceversa, può scrivere ma non
ha mai contatto diretto con contenuti non fidati. Questo isolamento
strutturale rende inefficaci i tentativi di prompt injection."

Correct output:
[
  {
    "question": "Spiega come il principio di separazione degli accessi rende inefficaci i tentativi di prompt injection.",
    "expected_answer": "Il reader, che è l'unico ad accedere a contenuti non fidati, non ha strumenti per scrivere file o interagire con sistemi tramite MCP. Il resolver, che ha accesso in scrittura, non vede mai contenuti non fidati. Quindi anche se un'istruzione malevola fosse iniettata nel reader, non potrebbe essere eseguita perché il reader non ha gli strumenti per agire.",
    "key_points": [
      "il reader vede contenuti non fidati ma non può scrivere",
      "il resolver può scrivere ma non vede contenuti non fidati",
      "le istruzioni iniettate non possono attraversare il confine tra i due ruoli",
      "isolamento strutturale, non basato su istruzioni testuali"
    ]
  }
]

WRONG output (yes/no question — too shallow for difficile):
[
  {
    "question": "Il reader ha accesso ai sistemi MCP?",
    "expected_answer": "No.",
    "key_points": ["no"]
  }
]
A binary recall question doesn't test synthesis. Wrong tier — would be
acceptable at facile, never at difficile.

WRONG output (introduces an outside example):
[
  {
    "question": "Come si applica il principio di separazione degli accessi al sistema OAuth?",
    "expected_answer": "...",
    "key_points": ["..."]
  }
]
OAuth is not in the source. Forbidden — outside knowledge.
"""


def openq_user_prompt(text: str, n: int, difficulty: Difficulty, language: str) -> str:
    return (
        f"Generate up to {n} open-ended questions from the following source.\n"
        f"Difficulty: {difficulty.value} — {_DIFFICULTY_DESCRIPTIONS[difficulty]}\n"
        f"Source language: {language}.\n\n"
        f"--- SOURCE TEXT ---\n{text}\n--- END SOURCE ---"
    )
