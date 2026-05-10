"""Bridge from `quiz_creation_agent` output to `eval_agent` input.

The two agents have intentionally different schemas — the quiz generator
uses a discriminated union over `item_type` ("f" / "mcq" / "qa") with
type-specific fields nested per item, while the evaluator takes a flat
`AssessmentItem` keyed by `assessment_type` ("flashcard" / "closed_quiz"
/ "open_question"). This module is the small adapter that converts
between them.

Usage:

    from quiz_creation_agent.orchestrator import generate_quiz
    from eval_agent.bridge import from_quiz_output
    from eval_agent.orchestrator import evaluate

    quiz = generate_quiz("data/markov.txt", item_type=ItemType.OPEN_QUESTION, n=3)
    items = from_quiz_output(quiz)
    trace = evaluate(items[0], student_response, session_id="demo")

The end-to-end pipeline (paragraph → items → evaluation) is the three
calls above. No schema negotiation in between.
"""

from __future__ import annotations

from typing import Any, Optional

from eval_agent.models import AssessmentItem, AssessmentType


_TYPE_MAP = {
    "f": AssessmentType.FLASHCARD,
    "mcq": AssessmentType.CLOSED_QUIZ,
    "qa": AssessmentType.OPEN_QUESTION,
}


def from_quiz_item(quiz_item: Any, *, language: str) -> AssessmentItem:
    """Convert a single quiz_creation_agent item to an `AssessmentItem`.

    Accepts either a Pydantic `FlashcardItem` / `MCQItem` / `OpenQuestionItem`
    (from `quiz_creation_agent.models`) or a dict-shaped equivalent.

    `node_id` is the link the eval agent uses for source-redirection. When
    a quiz was generated from a single node (the default path) it's there;
    when it was generated from a multi-node selection or raw text (the
    "Test on multiple sections" / "All document" UI flows) the source has
    no single node to point at. In that case we fall back to a synthetic
    id derived from the item itself — eval still works, but source-redirect
    interventions degrade to a generic "go back and re-read" hint instead
    of jumping to a specific paragraph.
    """
    d = _to_dict(quiz_item)

    item_type_str = d.get("item_type")
    if item_type_str not in _TYPE_MAP:
        raise ValueError(f"Unknown quiz item_type: {item_type_str!r}")

    source = d.get("source") or {}
    node_id = source.get("node_id") or f"merged:{d.get('item_id', 'unknown')}"

    locator_summary = _summarize_locator(
        source.get("locator"), source.get("source_label")
    )
    # Fallback when neither a label nor a locator was available (typical of
    # multi-node / "All document" quiz generation, which goes through the
    # raw-text path and loses the per-node anchor): point at the source
    # paragraph itself by quoting its first words. Worst case we mention
    # the filename. Anything beats "(unknown location)" — the user reads
    # the locator inside the intervention message.
    if locator_summary == "(unknown location)":
        excerpt = (source.get("excerpt") or "").strip().replace("\n", " ")
        filename = (source.get("source_filename") or "").strip()
        if excerpt:
            snippet = excerpt[:60] + ("…" if len(excerpt) > 60 else "")
            locator_summary = f'the paragraph starting with "{snippet}"'
        elif filename:
            locator_summary = filename
        else:
            locator_summary = "the document"

    common = dict(
        assessment_id=d["item_id"],
        node_id=node_id,
        assessment_type=_TYPE_MAP[item_type_str],
        source_excerpt=source.get("excerpt", ""),
        source_locator_summary=locator_summary,
        language=language,
    )

    if item_type_str == "f":
        return AssessmentItem(
            **common,
            question=d["front"],
            expected_answer=d["back"],
        )
    if item_type_str == "mcq":
        return AssessmentItem(
            **common,
            question=d["question"],
            options=d["options"],
            correct_index=d["correct_index"],
        )
    # item_type_str == "qa"
    return AssessmentItem(
        **common,
        question=d["question"],
        expected_answer=d["expected_answer"],
        key_points=d.get("key_points") or [],
    )


def from_quiz_output(quiz_output: Any) -> list[AssessmentItem]:
    """Convert a full `QuizOutput` (or its JSON-dict equivalent) into a list
    of `AssessmentItem`s. Inherits `language` from the quiz output, applies
    it to every item.
    """
    d = _to_dict(quiz_output)
    language = d.get("language")
    if language not in ("it", "en"):
        raise ValueError(f"QuizOutput.language must be 'it' or 'en', got {language!r}")
    return [from_quiz_item(item, language=language) for item in d.get("items", [])]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    raise TypeError(
        f"Expected a Pydantic model or dict, got {type(obj).__name__}"
    )


def _summarize_locator(
    locator: Optional[dict], source_label: Optional[str]
) -> str:
    """Human-readable position string. Accepts the polymorphic locator dict
    that quiz_creation_agent inherits from `processing_agent.models`.

    Examples:
      "§Civilta egizia, p.5"
      "§Markov property, p.47"
      "slide 12"
      "T 03:24-03:51"
      "char 1240-1890"
    """
    parts: list[str] = []
    if source_label:
        parts.append(f"§{source_label}")
    if isinstance(locator, dict):
        t = locator.get("type")
        if t == "pdf":
            ps, pe = locator.get("page_start"), locator.get("page_end")
            if ps and pe:
                parts.append(f"p.{ps}" if ps == pe else f"p.{ps}-{pe}")
        elif t == "slide":
            ss = locator.get("slide_index_start")
            se = locator.get("slide_index_end")
            if ss and se:
                parts.append(f"slide {ss}" if ss == se else f"slides {ss}-{se}")
        elif t == "md":
            cs = locator.get("char_offset_start")
            ce = locator.get("char_offset_end")
            if cs is not None and ce is not None:
                parts.append(f"char {cs}-{ce}")
        elif t == "time":
            ts = locator.get("t_start")
            te = locator.get("t_end")
            if ts is not None and te is not None:
                parts.append(f"T {_mmss(ts)}-{_mmss(te)}")
    return ", ".join(parts) if parts else "(unknown location)"


def _mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"
