"""LangGraph nodes for the evaluation agent.

One module rather than one-file-per-node: there are only ~12 nodes and
they all share the same state shape, so co-location keeps the wiring
readable.

Node responsibility map:

  detect_modality            — sets `response_text` from `response_raw` (text path)
  transcribe_audio           — runs Whisper on `response_raw` (audio path)
  extract_paralinguistic     — Phase 4 stub (currently emits empty features)
  detect_assessment_type     — pure routing helper (used as conditional edge)
  judge_closed               — exact match against expected option (no LLM)
  judge_flashcard            — normalize+match → LLM fuzzy fallback
  judge_open                 — 3-D rubric judge (LLM)
  apply_two_strikes_rule     — reads SessionState, sets `is_second_strike`
  route_intervention         — sets `intervention_kind` from judgment + strike
  generate_student_message   — builds `Intervention` (LLM call)
  emit_trace_event           — writes the event JSON to disk
  update_session_state       — mutates and re-saves SessionState

Every node early-returns when `state.errors` is non-empty.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from eval_agent.llm import call_json, call_text
from eval_agent.models import (
    AssessmentType,
    ClosedJudgment,
    ConceptStatusValue,
    Intervention,
    InterventionKind,
    OpenQuestionJudgment,
    ResponseModality,
    SourceRedirect,
    TraceEvent,
)
from eval_agent.prompts import (
    FLASHCARD_FUZZY_SYSTEM,
    GENERATE_MESSAGE_SYSTEM,
    JUDGE_OPEN_FEWSHOT,
    JUDGE_OPEN_SYSTEM,
    flashcard_fuzzy_user_prompt,
    generate_message_user_prompt,
    judge_open_user_prompt,
)
from eval_agent.session import save_session, session_dir
from eval_agent.state import EvalState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modality + audio path
# ---------------------------------------------------------------------------


def pass_through_text(state: EvalState) -> dict:
    """Text modality: response_text == response_raw."""
    if state.get("errors"):
        return {}
    if state["response_modality"] != ResponseModality.TEXT:
        return {}
    return {"response_text": state["response_raw"]}


def transcribe_audio(state: EvalState) -> dict:
    """Audio modality: run Whisper on `response_raw` (path) → transcript.

    Skipped when the test harness pre-populated `transcript` (and
    typically also `paralinguistic_features`) on the state — that path
    bypasses real audio entirely and lets us exercise the judge's
    paralinguistic-aware behavior with synthetic features.
    """
    if state.get("errors"):
        return {}
    if state["response_modality"] != ResponseModality.AUDIO:
        return {}
    if state.get("transcript"):  # already injected by test path
        return {}

    audio_path = state["response_raw"]
    try:
        from eval_agent.asr import transcribe

        result = transcribe(audio_path)
        transcript = " ".join(s.text for s in result.segments).strip()
        return {
            "transcript": transcript,
            "transcription_result": result,
            "response_text": transcript,
        }
    except Exception as e:
        logger.warning("Audio transcription failed: %s", e)
        return {
            "errors": [f"audio transcription failed: {e}"],
        }


def extract_paralinguistic(state: EvalState) -> dict:
    """Compute paralinguistic features from the TranscriptionResult.

    Skipped on text modality. If features were already injected (e.g. by
    a test harness pre-populating `paralinguistic_features` on the state),
    we leave them as-is — the orchestrator's injection path takes priority
    over re-extraction.
    """
    if state.get("errors"):
        return {}
    if state["response_modality"] != ResponseModality.AUDIO:
        return {}
    if state.get("paralinguistic_features"):
        return {}  # already injected upstream

    result = state.get("transcription_result")
    if result is None:
        return {"paralinguistic_features": {}}

    try:
        from eval_agent.paralinguistic import extract_features

        features = extract_features(result)
    except Exception as e:
        logger.warning("Paralinguistic extraction failed: %s", e)
        return {
            "paralinguistic_features": {},
            "warnings": [f"paralinguistic extraction failed: {e}"],
        }
    return {"paralinguistic_features": features}


# ---------------------------------------------------------------------------
# Closed quiz judge — pure string match, no LLM
# ---------------------------------------------------------------------------


def judge_closed(state: EvalState) -> dict:
    if state.get("errors"):
        return {}
    item = state["item"]
    response_text = (state.get("response_text") or "").strip()

    options = item.options or []
    correct_idx = item.correct_index
    if correct_idx is None or not options or correct_idx >= len(options):
        return {"errors": ["closed_quiz item is missing options or correct_index"]}

    expected_option = options[correct_idx]
    selected_idx = _parse_option_index(response_text, options)
    selected_option = options[selected_idx] if selected_idx is not None else response_text

    correct = (selected_idx == correct_idx)
    return {
        "judgment": ClosedJudgment(
            correct=correct,
            selected_option=selected_option,
            expected_option=expected_option,
        )
    }


def _parse_option_index(response: str, options: list[str]) -> int | None:
    """Try to parse the student's response as an option index.

    Accepts integer answers ("1", "2"), zero-/one-based; letter answers
    ("A", "B", "C", "D"); or free-text equal to one of the options.
    """
    s = response.strip()
    if not s:
        return None
    # Integer
    if s.isdigit():
        i = int(s)
        # Heuristic: 1-based answers if the value matches an option naturally
        if 1 <= i <= len(options):
            return i - 1
        if 0 <= i < len(options):
            return i
    # Letter (A, B, C, D)
    if len(s) == 1 and s.upper() in "ABCDEFGH":
        return ord(s.upper()) - ord("A")
    # Free text equal to an option (case-insensitive)
    norm = _normalize_text(s)
    for i, opt in enumerate(options):
        if _normalize_text(opt) == norm:
            return i
    return None


# ---------------------------------------------------------------------------
# Flashcard judge — normalize + exact, fallback to LLM fuzzy
# ---------------------------------------------------------------------------


def judge_flashcard(state: EvalState) -> dict:
    if state.get("errors"):
        return {}
    item = state["item"]
    expected = (item.expected_answer or "").strip()
    response_text = (state.get("response_text") or "").strip()
    if not expected:
        return {"errors": ["flashcard item is missing expected_answer"]}

    # Step 1: normalize+exact
    if _normalize_text(response_text) == _normalize_text(expected):
        return {
            "judgment": ClosedJudgment(
                correct=True,
                selected_option=response_text,
                expected_option=expected,
                fuzzy_match_score=1.0,
                fuzzy_match_used=False,
            )
        }

    # Step 2: LLM fuzzy
    try:
        resp = call_json(
            state["config"], "judge",
            system=FLASHCARD_FUZZY_SYSTEM,
            user=flashcard_fuzzy_user_prompt(item.question, expected, response_text),
        )
    except Exception as e:
        logger.warning("Flashcard fuzzy LLM failed: %s — defaulting to incorrect", e)
        return {
            "judgment": ClosedJudgment(
                correct=False,
                selected_option=response_text,
                expected_option=expected,
                fuzzy_match_used=True,
            ),
            "warnings": [f"fuzzy fallback unavailable: {str(e)[:140]}"],
        }

    correct = bool(resp.get("correct")) if isinstance(resp, dict) else False
    score = float(resp.get("score", 0.0)) if isinstance(resp, dict) else 0.0
    return {
        "judgment": ClosedJudgment(
            correct=correct,
            selected_option=response_text,
            expected_option=expected,
            fuzzy_match_score=score,
            fuzzy_match_used=True,
        )
    }


_PUNCT_RE = re.compile(r"[^\w\s]+")
_SPACE_RE = re.compile(r"\s+")


def _normalize_text(s: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, remove punctuation."""
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Open question judge — the centerpiece (LLM)
# ---------------------------------------------------------------------------


def judge_open(state: EvalState) -> dict:
    if state.get("errors"):
        return {}
    item = state["item"]
    response_text = (state.get("response_text") or "").strip()
    paralinguistic = state.get("paralinguistic_features") or None
    if paralinguistic == {}:
        paralinguistic = None  # treat empty dict as "no features"

    try:
        resp = call_json(
            state["config"], "judge",
            system=JUDGE_OPEN_SYSTEM,
            user=judge_open_user_prompt(
                question=item.question,
                source_paragraph=item.source_excerpt,
                expected_answer=item.expected_answer or "",
                key_points=item.key_points or [],
                student_response=response_text,
                paralinguistic_features=paralinguistic,
            ),
            fewshot=JUDGE_OPEN_FEWSHOT,
        )
    except Exception as e:
        logger.warning("judge_open LLM failed: %s", e)
        return {
            "errors": [f"judge_open LLM unavailable: {str(e).splitlines()[0][:200]}"],
        }

    if not isinstance(resp, dict):
        return {"errors": ["judge_open returned non-object response"]}

    judgment = _parse_open_judgment(resp)
    if judgment is None:
        return {"errors": ["judge_open returned malformed judgment"]}

    return {"judgment": judgment}


def _parse_open_judgment(d: dict) -> OpenQuestionJudgment | None:
    try:
        return OpenQuestionJudgment(
            completezza=d["completezza"],
            correttezza=d["correttezza"],
            elaborazione=d["elaborazione"],
            missing_aspects=d.get("missing_aspects") or [],
            incorrect_elements=d.get("incorrect_elements") or [],
            elaboration_evidence=d.get("elaboration_evidence", "") or "",
            paralinguistic_contribution=d.get("paralinguistic_contribution"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Two-strikes rule
# ---------------------------------------------------------------------------


def apply_two_strikes_rule(state: EvalState) -> dict:
    """Compute is_second_strike from SessionState's failed_attempts on this node."""
    if state.get("errors"):
        return {}
    sess = state["session_state"]
    node_id = state["item"].node_id
    concept = sess.get(node_id)
    return {"is_second_strike": concept.failed_attempts >= 1}


# ---------------------------------------------------------------------------
# Routing — judgment + is_second_strike → intervention_kind
# ---------------------------------------------------------------------------


def route_intervention(state: EvalState) -> dict:
    if state.get("errors"):
        return {}
    judgment = state.get("judgment")
    is_second = bool(state.get("is_second_strike"))
    item = state["item"]

    if isinstance(judgment, OpenQuestionJudgment):
        kind = _route_open(judgment, is_second)
    elif isinstance(judgment, ClosedJudgment):
        kind = _route_closed(judgment, is_second)
    else:
        return {"errors": ["route_intervention: missing or unknown judgment"]}

    return {"intervention_kind": kind.value}


def _route_open(j: OpenQuestionJudgment, is_second: bool) -> InterventionKind:
    if j.all_positive:
        return InterventionKind.ADVANCE
    if is_second:
        return InterventionKind.FULL_REDIRECT
    # Priority: correttezza > completezza > elaborazione
    if j.correttezza in ("parzialmente_corretta", "errata"):
        return InterventionKind.REDIRECT_ONLY
    if j.completezza in ("parziale", "assente"):
        return InterventionKind.HINT_PLUS_REDIRECT
    # By here: corretta + alta — only elaborazione can fail
    if j.elaborazione in ("riportata", "non_valutabile"):
        return InterventionKind.MODALITY_SWITCH
    return InterventionKind.ADVANCE


def _route_closed(j: ClosedJudgment, is_second: bool) -> InterventionKind:
    if j.correct:
        return InterventionKind.ADVANCE
    if is_second:
        return InterventionKind.FULL_REDIRECT
    return InterventionKind.HINT_PLUS_REDIRECT


# ---------------------------------------------------------------------------
# Student-facing message generation (LLM)
# ---------------------------------------------------------------------------


def generate_student_message(state: EvalState) -> dict:
    if state.get("errors"):
        return {}
    kind_str = state.get("intervention_kind")
    if kind_str is None:
        return {"errors": ["generate_student_message: no intervention_kind"]}

    item = state["item"]
    judgment = state.get("judgment")

    redirect = _build_redirect(item, kind_str)
    summary = _judgment_summary(judgment)

    try:
        message_text = call_text(
            state["config"], "message",
            system=GENERATE_MESSAGE_SYSTEM,
            user=generate_message_user_prompt(
                intervention_kind=kind_str,
                judgment_summary=summary,
                source_pointer=(redirect.locator_summary if redirect else None),
                language=item.language,
            ),
        )
    except Exception as e:
        logger.warning("generate_student_message LLM failed: %s", e)
        message_text = _fallback_message(kind_str, item, redirect)

    intervention = Intervention(
        kind=InterventionKind(kind_str),
        student_message=message_text,
        source_redirect=redirect,
    )
    return {"intervention": intervention}


def _build_redirect(item, kind_str: str) -> SourceRedirect | None:
    """Build a SourceRedirect when the intervention asks for it."""
    if kind_str == InterventionKind.ADVANCE.value:
        return None
    if kind_str == InterventionKind.MODALITY_SWITCH.value:
        return None  # modality switch doesn't redirect to source
    excerpt = (
        item.source_excerpt[:400] if kind_str == InterventionKind.FULL_REDIRECT.value
        else item.source_excerpt[:160]
    )
    return SourceRedirect(
        node_id=item.node_id,
        excerpt=excerpt,
        locator_summary=item.source_locator_summary,
    )


def _judgment_summary(judgment) -> str:
    if isinstance(judgment, OpenQuestionJudgment):
        parts = [
            f"completezza={judgment.completezza}",
            f"correttezza={judgment.correttezza}",
            f"elaborazione={judgment.elaborazione}",
        ]
        if judgment.missing_aspects:
            parts.append(f"missing={judgment.missing_aspects}")
        if judgment.incorrect_elements:
            parts.append(f"incorrect={judgment.incorrect_elements}")
        return "; ".join(parts)
    if isinstance(judgment, ClosedJudgment):
        return (
            f"correct={judgment.correct}; "
            f"selected={judgment.selected_option!r}; "
            f"expected={judgment.expected_option!r}"
        )
    return "unknown"


def _fallback_message(kind: str, item, redirect) -> str:
    """Conservative default if the LLM is unavailable. Defensive only."""
    lang = item.language
    if kind == InterventionKind.ADVANCE.value:
        return "Ottimo, andiamo avanti." if lang == "it" else "Great, let's move on."
    pointer = (
        f" Dai un'occhiata a {redirect.locator_summary}." if redirect and lang == "it"
        else (f" Have a look at {redirect.locator_summary}." if redirect else "")
    )
    base = {
        InterventionKind.HINT_PLUS_REDIRECT.value: (
            "Non ci siamo del tutto. Manca un pezzo della risposta." if lang == "it"
            else "Almost there — a piece of the answer is missing."
        ),
        InterventionKind.REDIRECT_ONLY.value: (
            "Rivedi il sorgente e riprova." if lang == "it"
            else "Take another look at the source and try again."
        ),
        InterventionKind.MODALITY_SWITCH.value: (
            "Prova a riformulare con parole tue, magari con un esempio." if lang == "it"
            else "Try reformulating in your own words, maybe with an example."
        ),
        InterventionKind.FULL_REDIRECT.value: (
            "Torniamo al sorgente prima di proseguire." if lang == "it"
            else "Let's go back to the source before we continue."
        ),
    }.get(kind, "")
    return (base + pointer).strip()


# ---------------------------------------------------------------------------
# Trace event emission + session update
# ---------------------------------------------------------------------------


def emit_trace_event(state: EvalState) -> dict:
    """Build the TraceEvent and write it to disk."""
    if state.get("errors"):
        return {}
    item = state["item"]
    judgment = state["judgment"]
    intervention = state["intervention"]
    sess = state["session_state"]
    concept = sess.get(item.node_id)

    is_pass = (intervention.kind == InterventionKind.ADVANCE)
    is_full_redirect = (intervention.kind == InterventionKind.FULL_REDIRECT)
    if is_pass:
        new_status = ConceptStatusValue.PASSED
    elif is_full_redirect:
        new_status = ConceptStatusValue.FRAGILE
    else:
        new_status = ConceptStatusValue.PENDING

    event = TraceEvent(
        session_id=state["session_id"],
        node_id=item.node_id,
        assessment_type=item.assessment_type,
        assessment_id=item.assessment_id,
        attempt_number=concept.failed_attempts + 1,
        response_modality=state["response_modality"],
        response_raw=state.get("response_text") or state["response_raw"],
        paralinguistic_features=state.get("paralinguistic_features") or None,
        judgment=judgment,
        intervention=intervention,
        concept_status_after=new_status,
    )

    out_dir = session_dir(state["session_id"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{event.event_id}.json"
    out_file.write_text(
        event.model_dump_json(indent=2), encoding="utf-8"
    )
    logger.info("Wrote trace event %s", out_file)
    return {
        "trace_event": event,
        "concept_status_after": new_status.value,
    }


def update_session_state(state: EvalState) -> dict:
    """Mutate SessionState with this turn's outcome and persist."""
    if state.get("errors"):
        return {}
    sess = state["session_state"]
    item = state["item"]
    judgment = state["judgment"]
    intervention = state["intervention"]
    concept = sess.get(item.node_id)

    concept.attempts += 1
    if intervention.kind == InterventionKind.ADVANCE:
        concept.status = ConceptStatusValue.PASSED
    else:
        concept.failed_attempts += 1
        if intervention.kind == InterventionKind.FULL_REDIRECT:
            concept.status = ConceptStatusValue.FRAGILE
        else:
            concept.status = ConceptStatusValue.PENDING

    concept.rubric_history.append(judgment.model_dump(mode="json"))
    concept.intervention_history.append(intervention.model_dump(mode="json"))

    save_session(sess)

    payload: dict[str, Any] = state["trace_event"].model_dump(mode="json")
    return {"session_state": sess, "output_payload": payload}


# ---------------------------------------------------------------------------
# Conditional edge selectors (used by graph.py)
# ---------------------------------------------------------------------------


def route_by_modality(state: EvalState) -> str:
    return (
        "audio" if state["response_modality"] == ResponseModality.AUDIO else "text"
    )


def route_by_assessment_type(state: EvalState) -> str:
    if state.get("errors"):
        return "halt"
    t = state["item"].assessment_type
    if t == AssessmentType.CLOSED_QUIZ:
        return "closed"
    if t == AssessmentType.FLASHCARD:
        return "flashcard"
    if t == AssessmentType.OPEN_QUESTION:
        return "open"
    return "halt"
