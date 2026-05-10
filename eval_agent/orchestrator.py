"""Top-level entry point for the evaluation agent.

Public API:
- `evaluate(item, response, session_id, ...)` — run one evaluation turn
- `make_config(use_pro=False)`                — exposed from llm.py for callers
                                                that want to share config across
                                                multiple evaluate() calls

The function loads SessionState, runs the graph, persists results, and
returns the TraceEvent payload as a dict.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from eval_agent.graph import build_graph
from eval_agent.llm import make_config
from eval_agent.models import (
    AssessmentItem,
    LLMConfig,
    ResponseModality,
)
from eval_agent.session import load_session
from eval_agent.state import initial_state

logger = logging.getLogger(__name__)


_compiled_graph = None


def _graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def evaluate(
    item: AssessmentItem,
    response: str | Path,
    session_id: str,
    *,
    response_modality: ResponseModality = ResponseModality.TEXT,
    config: Optional[LLMConfig] = None,
    use_pro: bool = False,
    paralinguistic_features: Optional[dict] = None,
) -> dict[str, Any]:
    """Evaluate one student response. Returns the TraceEvent JSON payload.

    Parameters
    ----------
    item:
        The `AssessmentItem` to evaluate against.
    response:
        Either a text string (when `response_modality=TEXT`) or a path to
        an audio file (when `response_modality=AUDIO`).
    session_id:
        Identifier for the session; drives the two-strikes rule and trace
        directory layout (`data/traces/<session_id>/`).
    config:
        Pre-built `LLMConfig`. If omitted, builds one based on `use_pro`
        and env vars. Useful when callers run many evaluations and want
        to amortize the validation step.
    use_pro:
        If True (and `config` is None), build a config that routes the
        judge to Gemini 2.5 Pro using `GEMINI_PRO_API_KEY`. Default False.
    paralinguistic_features:
        Pre-computed features dict to inject directly into the state,
        bypassing the audio transcription + extraction pipeline. Useful
        for testing the judge's paralinguistic-aware behavior without a
        real audio recording. When set, this also forces the judge to
        treat the response as audio-modality regardless of `response_modality`.

    Raises
    ------
    RuntimeError
        If the graph reports terminal errors (missing key, malformed item,
        irrecoverable LLM failure).
    """
    if not item.node_id:
        raise ValueError("AssessmentItem rejected: node_id is mandatory")

    cfg = config or make_config(use_pro=use_pro)
    session_state = load_session(session_id)

    effective_modality = response_modality
    if paralinguistic_features is not None:
        # Test path: features are injected directly. Treat as audio so the
        # judge prompt reads the features, but skip transcription (the
        # response is already textual).
        effective_modality = ResponseModality.AUDIO

    state = initial_state(
        session_id=session_id,
        item=item,
        response_modality=effective_modality,
        response_raw=str(response),
        config=cfg,
        session_state=session_state,
    )
    if paralinguistic_features is not None:
        state["paralinguistic_features"] = paralinguistic_features
        state["response_text"] = str(response)
        state["transcript"] = str(response)

    result = _graph().invoke(state)
    if result.get("errors"):
        raise RuntimeError(f"Evaluation failed: {' | '.join(result['errors'])}")

    payload = result.get("output_payload")
    if payload is None:
        raise RuntimeError("Evaluation finished but produced no trace event.")
    return payload
