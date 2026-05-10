"""Core generation logic.

Single LLM call per request, batched: one call produces N items at the
requested difficulty. The LLM is allowed to return fewer items than
requested (the prompt says so explicitly) — we trust that signal rather
than padding with low-quality fillers.

Item validation is defensive: malformed entries are dropped with a warning,
not raised, so a partially-good response still yields a usable QuizOutput.
"""

from __future__ import annotations

import logging
from typing import Optional

from quiz_creation_agent.llm import call_json
from quiz_creation_agent.models import (
    AssessmentItem,
    Difficulty,
    FlashcardItem,
    ItemType,
    MCQItem,
    OpenQuestionItem,
    QuizMetadata,
    QuizOutput,
    SourceRef,
)
from quiz_creation_agent.prompts import (
    FLASHCARD_FEWSHOT,
    FLASHCARD_SYSTEM,
    MCQ_FEWSHOT,
    MCQ_SYSTEM,
    OPENQ_FEWSHOT,
    OPENQ_SYSTEM,
    flashcard_user_prompt,
    mcq_user_prompt,
    openq_user_prompt,
)

logger = logging.getLogger(__name__)


# Hard cap on items per request. Larger N strains both prompt size and
# quality (the LLM starts repeating itself or padding). Demo values typically
# 3-10. A single call covers the whole batch.
MAX_N = 25


def generate_items(
    *,
    text: str,
    item_type: ItemType,
    n: int,
    difficulty: Difficulty,
    language: str,
    source: SourceRef,
) -> QuizOutput:
    """Generate `n` items of the requested type and difficulty from `text`."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if n > MAX_N:
        logger.warning("Requested n=%d capped to %d", n, MAX_N)
        n = MAX_N

    warnings: list[str] = []
    try:
        response = _call_llm(item_type, text, n, difficulty, language)
    except Exception as e:
        logger.warning("Quiz generation LLM call failed: %s", e)
        warnings.append(f"LLM call failed: {str(e).splitlines()[0][:200]}")
        response = []

    items = _parse_response(response, item_type, difficulty, source, warnings)

    return QuizOutput(
        item_type=item_type,
        difficulty=difficulty,
        language=language,
        n_requested=n,
        n_produced=len(items),
        source=source,
        items=items,
        metadata=QuizMetadata(warnings=warnings),
    )


# ---------------------------------------------------------------------------
# LLM dispatch
# ---------------------------------------------------------------------------


def _call_llm(item_type: ItemType, text: str, n: int, difficulty: Difficulty, language: str):
    if item_type == ItemType.FLASHCARD:
        return call_json(
            system=FLASHCARD_SYSTEM,
            user=flashcard_user_prompt(text, n, difficulty, language),
            fewshot=FLASHCARD_FEWSHOT,
        )
    if item_type == ItemType.MCQ:
        return call_json(
            system=MCQ_SYSTEM,
            user=mcq_user_prompt(text, n, difficulty, language),
            fewshot=MCQ_FEWSHOT,
        )
    if item_type == ItemType.OPEN_QUESTION:
        return call_json(
            system=OPENQ_SYSTEM,
            user=openq_user_prompt(text, n, difficulty, language),
            fewshot=OPENQ_FEWSHOT,
        )
    raise ValueError(f"Unknown item_type: {item_type}")


# ---------------------------------------------------------------------------
# Response parsing — defensive, never raises
# ---------------------------------------------------------------------------


def _parse_response(
    response,
    item_type: ItemType,
    difficulty: Difficulty,
    source: SourceRef,
    warnings: list[str],
) -> list[AssessmentItem]:
    if not isinstance(response, list):
        warnings.append("LLM response was not a JSON array; produced 0 items")
        return []

    out: list[AssessmentItem] = []
    for i, raw in enumerate(response):
        if not isinstance(raw, dict):
            warnings.append(f"item #{i}: not a JSON object; skipped")
            continue
        try:
            item = _parse_one(raw, item_type, difficulty, source)
        except Exception as e:
            warnings.append(f"item #{i}: {str(e)[:140]}")
            continue
        if item is not None:
            out.append(item)
    return out


def _parse_one(
    raw: dict,
    item_type: ItemType,
    difficulty: Difficulty,
    source: SourceRef,
) -> Optional[AssessmentItem]:
    if item_type == ItemType.FLASHCARD:
        front = _str(raw.get("front"))
        back = _str(raw.get("back"))
        if not (front and back):
            return None
        return FlashcardItem(difficulty=difficulty, source=source, front=front, back=back)

    if item_type == ItemType.MCQ:
        question = _str(raw.get("question"))
        options = raw.get("options")
        ci = raw.get("correct_index")
        explanation = _str(raw.get("explanation"))
        if not question or not isinstance(options, list) or len(options) != 4:
            return None
        if not all(isinstance(o, str) and o.strip() for o in options):
            return None
        if not isinstance(ci, int) or not (0 <= ci <= 3):
            return None
        return MCQItem(
            difficulty=difficulty, source=source,
            question=question, options=[o.strip() for o in options],
            correct_index=ci, explanation=explanation or "",
        )

    if item_type == ItemType.OPEN_QUESTION:
        question = _str(raw.get("question"))
        expected = _str(raw.get("expected_answer"))
        kp = raw.get("key_points")
        if not question or not expected:
            return None
        if not isinstance(kp, list):
            kp = []
        kp = [str(p).strip() for p in kp if str(p).strip()]
        return OpenQuestionItem(
            difficulty=difficulty, source=source,
            question=question, expected_answer=expected, key_points=kp,
        )

    return None


def _str(v) -> str:
    return v.strip() if isinstance(v, str) else ""
