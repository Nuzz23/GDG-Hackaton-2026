"""Domain models for the indexing agent.

Three layers of data:

1. `Block` + `SourceLocator` — pre-segmentation atomic units produced by the
   format-specific parsers. After `normalize_to_blocks` the rest of the graph
   does not care which parser produced them.
2. `SemanticParagraph` — coherent units of meaning produced by the
   segmentation step. They become the leaves of the final tree.
3. `HierarchyNode` and `IndexOutput` — the final tree and its serialized
   wrapper, written to `index.json`.

`SourceLocator` is a discriminated union over a `type` field. Every node in
the final tree carries a locator that points back into the source — this is
the project's non-negotiable traceability constraint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    PDF = "pdf"
    PDF_NOTES = "pdf_notes"
    PDF_SLIDES = "pdf_slides"
    PPTX = "pptx"
    MD = "md"
    AUDIO = "audio"
    VIDEO = "video"


class Language(str, Enum):
    IT = "it"
    EN = "en"


class BlockKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    SLIDE_TITLE = "slide_title"
    SLIDE_BULLET = "slide_bullet"
    SLIDE_BODY = "slide_body"
    UTTERANCE = "utterance"


class NodeKind(str, Enum):
    ROOT = "root"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"


# ---------------------------------------------------------------------------
# Source locators (polymorphic, discriminated by `type`)
# ---------------------------------------------------------------------------


class _LocatorBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PDFLocator(_LocatorBase):
    type: Literal["pdf"] = "pdf"
    page_start: int
    page_end: int
    char_range: Optional[tuple[int, int]] = None
    bbox: Optional[tuple[float, float, float, float]] = None


class SlideLocator(_LocatorBase):
    type: Literal["slide"] = "slide"
    slide_index_start: int
    slide_index_end: int


class MarkdownLocator(_LocatorBase):
    type: Literal["md"] = "md"
    char_offset_start: int
    char_offset_end: int


class TimeLocator(_LocatorBase):
    type: Literal["time"] = "time"
    t_start: float
    t_end: float


SourceLocator = Annotated[
    Union[PDFLocator, SlideLocator, MarkdownLocator, TimeLocator],
    Field(discriminator="type"),
]


def union_locators(locators: list[SourceLocator]) -> SourceLocator:
    """Return the smallest locator that covers all the given locators.

    All locators must be of the same kind. Used to compute the locator of an
    internal node from its children.
    """
    if not locators:
        raise ValueError("union_locators requires at least one locator")
    kinds = {l.type for l in locators}
    if len(kinds) != 1:
        raise ValueError(f"cannot union locators of mixed kinds: {kinds}")
    kind = kinds.pop()
    if kind == "pdf":
        return PDFLocator(
            page_start=min(l.page_start for l in locators),  # type: ignore[attr-defined]
            page_end=max(l.page_end for l in locators),  # type: ignore[attr-defined]
        )
    if kind == "slide":
        return SlideLocator(
            slide_index_start=min(l.slide_index_start for l in locators),  # type: ignore[attr-defined]
            slide_index_end=max(l.slide_index_end for l in locators),  # type: ignore[attr-defined]
        )
    if kind == "md":
        return MarkdownLocator(
            char_offset_start=min(l.char_offset_start for l in locators),  # type: ignore[attr-defined]
            char_offset_end=max(l.char_offset_end for l in locators),  # type: ignore[attr-defined]
        )
    if kind == "time":
        return TimeLocator(
            t_start=min(l.t_start for l in locators),  # type: ignore[attr-defined]
            t_end=max(l.t_end for l in locators),  # type: ignore[attr-defined]
        )
    raise ValueError(f"unknown locator kind: {kind}")


# ---------------------------------------------------------------------------
# Block — pre-segmentation atomic unit
# ---------------------------------------------------------------------------


class Block(BaseModel):
    """A pre-segmentation atomic unit produced by a parser.

    Blocks are NOT the leaves of the final tree. The segmentation step groups
    blocks into `SemanticParagraph`s, which become the leaves.

    The `meta` dict carries parser-specific signals (font_size, heading_level,
    indent depth, speaker, ...) that the structure-detection node can use to
    decide between the structured and the semantic branch.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"b_{uuid4().hex[:10]}")
    kind: BlockKind
    text: str
    locator: SourceLocator
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Document — output of parsing, input of the rest of the graph
# ---------------------------------------------------------------------------


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    source_type: SourceType
    blocks: list[Block]
    size_metric: dict[str, Any] = Field(default_factory=dict)
    parser_meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Semantic paragraph — leaf of the tree
# ---------------------------------------------------------------------------


class SemanticParagraph(BaseModel):
    """A coherent unit of meaning. Becomes a leaf in the final tree.

    `block_ids` is the ordered list of source blocks composing the paragraph.
    `text` is the concatenation of those blocks' text (verbatim for textual
    sources, cleaned for audio/video). `locator` is the union of the blocks'
    locators.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"p_{uuid4().hex[:10]}")
    block_ids: list[str]
    text: str
    locator: SourceLocator


# ---------------------------------------------------------------------------
# Hierarchy tree — final structure
# ---------------------------------------------------------------------------


class HierarchyNode(BaseModel):
    """A node in the final tree.

    `text` is populated only on leaf nodes (paragraphs). Internal nodes have
    only a generated `label`. The `locator` of an internal node is the union
    of its children's locators — this is computed bottom-up at construction
    time, never re-derived elsewhere.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    level: int
    kind: NodeKind
    label: Optional[str] = None
    text: Optional[str] = None
    locator: SourceLocator
    children: list["HierarchyNode"] = Field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children


HierarchyNode.model_rebuild()


# ---------------------------------------------------------------------------
# Output schema (the on-disk index.json)
# ---------------------------------------------------------------------------


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: SourceType
    filename: str
    language: Language
    size_metric: dict[str, Any]


class OutputMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_version: str = "0.1.0"
    warnings: list[str] = Field(default_factory=list)


class IndexOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    source: SourceInfo
    tree: HierarchyNode
    metadata: OutputMetadata = Field(default_factory=OutputMetadata)
