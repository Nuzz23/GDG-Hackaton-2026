"""LangGraph state schema for the evaluation agent."""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from eval_agent.models import (
    AssessmentItem,
    AssessmentType,
    Intervention,
    Judgment,
    LLMConfig,
    ResponseModality,
    SessionState,
    TraceEvent,
)


class EvalState(TypedDict, total=False):
    """State carried through the LangGraph pipeline.

    `total=False` so each node can return a partial dict. Errors and
    warnings accumulate via the `add` reducer so multiple nodes can append
    independently.
    """

    # Input
    session_id: str
    item: AssessmentItem
    response_modality: ResponseModality
    response_raw: str  # text string, OR audio file path when modality=audio
    config: LLMConfig

    # Filled by audio path
    transcript: Optional[str]
    transcription_result: Optional[object]  # TranscriptionResult dataclass; opaque to typing
    paralinguistic_features: Optional[dict]

    # Promoted convenience field — for text modality this == response_raw,
    # for audio it == transcript. Downstream judges read this uniformly.
    response_text: Optional[str]

    # Filled by judges
    judgment: Optional[Judgment]

    # Filled by routing
    is_second_strike: bool
    intervention_kind: Optional[str]
    intervention: Optional[Intervention]
    concept_status_after: Optional[str]

    # Session memory
    session_state: SessionState

    # Output
    trace_event: Optional[TraceEvent]
    output_payload: Optional[dict]

    # Diagnostics
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]


def initial_state(
    *,
    session_id: str,
    item: AssessmentItem,
    response_modality: ResponseModality,
    response_raw: str,
    config: LLMConfig,
    session_state: SessionState,
) -> EvalState:
    return EvalState(
        session_id=session_id,
        item=item,
        response_modality=response_modality,
        response_raw=response_raw,
        config=config,
        session_state=session_state,
        transcript=None,
        paralinguistic_features=None,
        response_text=None,
        judgment=None,
        is_second_strike=False,
        intervention_kind=None,
        intervention=None,
        concept_status_after=None,
        trace_event=None,
        output_payload=None,
        errors=[],
        warnings=[],
    )
