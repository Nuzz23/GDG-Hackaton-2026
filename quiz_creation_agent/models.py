"""Domain models for the quiz generator.

Three item types as a discriminated union over `item_type`:

- "f"   — Flashcard (front/back)
- "mcq" — Multiple-choice question (4 options, one correct)
- "qa"  — Open question (free-text answer, with expected outline)

All items carry a `SourceRef` pointing back to the paragraph/section the
item was generated from. When the source was an `index.json`, the ref is
fully populated with `doc_id`, `node_id`, `locator` so the eval agent (and
Braynr) can navigate from the item back to the original passage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Difficulty(str, Enum):
    FACILE = "facile"
    MEDIO = "medio"
    DIFFICILE = "difficile"


class ItemType(str, Enum):
    FLASHCARD = "f"
    MCQ = "mcq"
    OPEN_QUESTION = "qa"


class SourceRef(BaseModel):
    """Provenance of the text the item was generated from.

    `doc_id`, `node_id`, `source_label`, `locator` are set when input came
    from an `IndexOutput` (the per-document agent's output). `source_filename`
    is always set. `excerpt` is a short verbatim slice of the source text
    for sanity-checking and downstream display.
    """

    model_config = ConfigDict(extra="forbid")

    source_filename: str
    excerpt: str

    doc_id: Optional[str] = None
    node_id: Optional[str] = None
    source_label: Optional[str] = None
    # Kept as an opaque dict to avoid coupling with `agent.models.SourceLocator`.
    # The shape mirrors that union (PDFLocator, SlideLocator, MarkdownLocator,
    # TimeLocator) — see `agent/models.py`.
    locator: Optional[dict] = None


class _BaseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str = Field(default_factory=lambda: f"q_{uuid4().hex[:10]}")
    difficulty: Difficulty
    source: SourceRef


class FlashcardItem(_BaseItem):
    """Spaced-repetition flashcard. Front cues recall, back is the answer."""
    item_type: Literal["f"] = "f"
    front: str
    back: str


class MCQItem(_BaseItem):
    """Multiple-choice item. Always 4 options, one correct."""
    item_type: Literal["mcq"] = "mcq"
    question: str
    options: list[str]
    correct_index: int  # 0..3
    explanation: str  # why the correct answer is right; useful for eval feedback


class OpenQuestionItem(_BaseItem):
    """Open-ended question — user writes a free-text answer."""
    item_type: Literal["qa"] = "qa"
    question: str
    expected_answer: str       # outline of a good answer (for eval)
    key_points: list[str]      # 3-5 phrases the answer should cover


AssessmentItem = Annotated[
    Union[FlashcardItem, MCQItem, OpenQuestionItem],
    Field(discriminator="item_type"),
]


class QuizMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_version: str = "0.1.0"
    warnings: list[str] = Field(default_factory=list)


class QuizOutput(BaseModel):
    """Top-level on-disk schema for a single generation request."""

    model_config = ConfigDict(extra="forbid")

    quiz_id: str = Field(default_factory=lambda: str(uuid4()))
    item_type: ItemType
    difficulty: Difficulty
    language: str  # "it" | "en"
    n_requested: int
    n_produced: int
    source: SourceRef
    items: list[AssessmentItem]
    metadata: QuizMetadata = Field(default_factory=QuizMetadata)
