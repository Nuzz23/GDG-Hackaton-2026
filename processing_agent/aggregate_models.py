"""Models for the aggregate (cross-document) index.

The aggregator takes N already-indexed documents and produces a single
navigable tree that organizes their *sections* into a higher-level
structure. Unlike `IndexOutput`, an aggregate's leaves do NOT carry source
text — they carry references back to specific nodes in source documents.

Three layers, mirroring the per-document agent:

1. `SourceSummary` — one entry per source document (filename, language, etc).
2. `DocumentRef` — pointer to a specific (doc_id, node_id) section.
3. `AggregateNode` — tree node, either a category (with children) or a leaf
   ref (with `ref` set, no children).

The output is `AggregateOutput`, designed to be JSON-stable and consumable
by the same Braynr backend that consumes `IndexOutput`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class OrganizingPrinciple(str, Enum):
    CHRONOLOGICAL = "chronological"
    TOPICAL = "topical"
    ALPHABETICAL = "alphabetical"
    STRUCTURAL = "structural"


class AggregateNodeKind(str, Enum):
    ROOT = "root"
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    REF = "ref"


class SourceSummary(BaseModel):
    """One entry per source document the aggregator consumed."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    filename: str
    language: str
    size_metric: dict


class DocumentRef(BaseModel):
    """Pointer to a specific section in a source document.

    The aggregate's leaves carry one of these. Together with the source
    document's `doc_id` (also stored on the ref) the backend can resolve
    the click to the exact section in the original `index.json`.
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    node_id: str
    source_filename: str
    source_label: str  # the label as it appears in the source index, for traceability
    source_kind: str  # "chapter" or "section"


class AggregateNode(BaseModel):
    """Node in the aggregate tree.

    A node is either a CATEGORY/SUBCATEGORY (has `children`, no `ref`) or a
    REF leaf (has `ref` set, no children). The validator below enforces the
    invariant.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    level: int
    kind: AggregateNodeKind
    label: Optional[str] = None
    ref: Optional[DocumentRef] = None
    children: list["AggregateNode"] = Field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return self.kind == AggregateNodeKind.REF


AggregateNode.model_rebuild()


class AggregateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_version: str = "0.1.0"
    warnings: list[str] = Field(default_factory=list)
    n_sources: int = 0
    n_refs: int = 0


class AggregateOutput(BaseModel):
    """Top-level on-disk schema for an aggregate index.json."""

    model_config = ConfigDict(extra="forbid")

    aggregate_id: str = Field(default_factory=lambda: str(uuid4()))
    organizing_principle: OrganizingPrinciple
    principle_rationale: str
    sources: list[SourceSummary]
    tree: AggregateNode
    metadata: AggregateMetadata = Field(default_factory=AggregateMetadata)
