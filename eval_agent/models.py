"""Domain models for the evaluation agent.

The schemas here are the contracts with upstream (assessment generators) and
downstream (Braynr backend, future agents). Layered as:

- `AssessmentItem`         input contract — what arrives to be evaluated
- `OpenQuestionJudgment` / `ClosedJudgment` discriminated union
- `Intervention` + `SourceRedirect`
- `TraceEvent`             output contract — one per turn
- `ConceptStatus` + `SessionState`  intra-session memory
- `LLMConfig`              wraps Flash + (optional) Pro routing
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums (use string values so JSON is human-readable)
# ---------------------------------------------------------------------------


class AssessmentType(str, Enum):
    CLOSED_QUIZ = "closed_quiz"
    FLASHCARD = "flashcard"
    OPEN_QUESTION = "open_question"


class ResponseModality(str, Enum):
    TEXT = "text"
    AUDIO = "audio"


class ConceptStatusValue(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FRAGILE = "fragile"


class InterventionKind(str, Enum):
    ADVANCE = "advance"
    HINT_PLUS_REDIRECT = "hint_plus_redirect"
    REDIRECT_ONLY = "redirect_only"
    MODALITY_SWITCH = "modality_switch"
    FULL_REDIRECT = "full_redirect"


# ---------------------------------------------------------------------------
# Input contract — AssessmentItem
# ---------------------------------------------------------------------------


class AssessmentItem(BaseModel):
    """Item to be evaluated. Comes from upstream assessment generation.

    Flat schema across all three types — type-specific fields are Optional
    and validated based on `assessment_type`. Looser than a discriminated
    union, but the discriminator (`assessment_type`) drives the graph
    routing, not Pydantic — so a flat shape is simpler at the agent
    boundary.
    """

    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    node_id: str  # link to Part 2 index — MANDATORY
    assessment_type: AssessmentType
    question: str

    # closed_quiz fields
    options: Optional[list[str]] = None
    correct_index: Optional[int] = None

    # flashcard fields: expected_answer holds the back of the card
    # open_question fields: expected_answer is the outline; key_points is the rubric
    expected_answer: Optional[str] = None
    key_points: Optional[list[str]] = None

    # Source provenance — needed for redirect interventions
    source_excerpt: str
    source_locator_summary: str  # e.g. "§3.2, p.47"
    language: Literal["it", "en"]


# ---------------------------------------------------------------------------
# Judgments — discriminated by `judgment_type`
# ---------------------------------------------------------------------------


class OpenQuestionJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgment_type: Literal["open"] = "open"
    completezza: Literal["alta", "parziale", "assente"]
    correttezza: Literal["corretta", "parzialmente_corretta", "errata"]
    elaborazione: Literal["rielaborata", "riportata", "non_valutabile"]
    missing_aspects: list[str] = Field(default_factory=list)
    incorrect_elements: list[str] = Field(default_factory=list)
    elaboration_evidence: str = ""
    paralinguistic_contribution: Optional[str] = None  # populated in Phase 4

    @property
    def all_positive(self) -> bool:
        return (
            self.completezza == "alta"
            and self.correttezza == "corretta"
            and self.elaborazione == "rielaborata"
        )


class ClosedJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgment_type: Literal["closed"] = "closed"
    correct: bool
    selected_option: str
    expected_option: str
    fuzzy_match_score: Optional[float] = None
    fuzzy_match_used: bool = False  # whether LLM fallback was invoked


Judgment = Annotated[
    Union[OpenQuestionJudgment, ClosedJudgment],
    Field(discriminator="judgment_type"),
]


# ---------------------------------------------------------------------------
# Intervention
# ---------------------------------------------------------------------------


class SourceRedirect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str
    excerpt: Optional[str] = None
    locator_summary: str  # human-readable position, e.g. "§3.2, p.47"


class Intervention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: InterventionKind
    student_message: str
    source_redirect: Optional[SourceRedirect] = None


# ---------------------------------------------------------------------------
# TraceEvent — output contract, one per turn
# ---------------------------------------------------------------------------


class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    node_id: str
    assessment_type: AssessmentType
    assessment_id: str
    attempt_number: int  # 1 or 2 (capped by two-strikes rule)
    response_modality: ResponseModality
    response_raw: str  # text or transcript
    paralinguistic_features: Optional[dict] = None
    judgment: Judgment
    intervention: Intervention
    concept_status_after: ConceptStatusValue


# ---------------------------------------------------------------------------
# Session memory
# ---------------------------------------------------------------------------


class ConceptStatus(BaseModel):
    """Per-node memory across a session. Drives the two-strikes rule.

    `failed_attempts` is the relevant counter: a "second strike" occurs when
    we are about to log a failure on a node that already has
    `failed_attempts >= 1`. On the second failure the concept is marked
    `fragile` and downstream is signalled to handle re-surfacing.
    """

    model_config = ConfigDict(extra="forbid")
    node_id: str
    attempts: int = 0
    failed_attempts: int = 0
    rubric_history: list[dict] = Field(default_factory=list)
    intervention_history: list[dict] = Field(default_factory=list)
    status: ConceptStatusValue = ConceptStatusValue.PENDING


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    concepts: dict[str, ConceptStatus] = Field(default_factory=dict)

    def get(self, node_id: str) -> ConceptStatus:
        return self.concepts.setdefault(
            node_id, ConceptStatus(node_id=node_id)
        )


# ---------------------------------------------------------------------------
# LLM configuration — Flash default, Pro for judge_open under --pro
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """Resolved at startup (after CLI parsing). Read-only afterward.

    - In default mode, both `judge_*` and `message_*` are Flash and use
      `GOOGLE_API_KEY` (or `GEMINI_API_KEY`).
    - In `--pro` mode, `judge_model` becomes `gemini-2.5-pro` with
      `GEMINI_PRO_API_KEY`; `message_*` stays on Flash with the Flash key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    judge_model: str
    message_model: str
    judge_api_key: str
    message_api_key: str
