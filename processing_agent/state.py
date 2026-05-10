"""LangGraph state schema.

A single typed state object flows through every node. Each node returns a
partial state dict — LangGraph merges it. List fields use `add_messages`-like
accumulation by being explicitly replaced (not appended) by node returns,
except `errors` and `warnings`, which we accumulate via reducer functions.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from processing_agent.models import (
    Block,
    Document,
    HierarchyNode,
    Language,
    SemanticParagraph,
    SourceType,
)


class IndexingState(TypedDict, total=False):
    """State carried through the LangGraph pipeline.

    `total=False` so that nodes can return partial updates without having to
    populate every field. Fields default to absent until the relevant node
    populates them.
    """

    # Set at entry, never mutated downstream.
    source_path: str
    source_type: SourceType

    # Populated by `detect_language` (text formats) or `parse_audio` (a/v).
    language: Optional[Language]

    # Populated by parsers.
    document: Optional[Document]

    # Populated by `normalize_to_blocks` — same content as `document.blocks`,
    # promoted to top-level for easy access by downstream nodes.
    blocks: list[Block]

    # Populated by `detect_typographic_structure`.
    has_typographic_structure: bool

    # Populated by either `build_hierarchy_from_structure` (structured branch)
    # or by `semantic_segmentation` + `hierarchical_clustering` (semantic branch).
    paragraphs: list[SemanticParagraph]
    hierarchy: Optional[HierarchyNode]

    # Accumulated across the run. Reducer is `operator.add` so multiple nodes
    # appending warnings does the right thing without manual merging.
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]

    # Set by the orchestrator if the caller wants the final index written
    # to disk; left unset for in-memory use.
    output_path: Optional[str]

    # Populated by `validate_and_serialize` — the JSON-serializable payload.
    output: Optional[dict]


def initial_state(
    source_path: str, source_type: Optional[SourceType] = None
) -> IndexingState:
    """Build the starting state for a graph run.

    Pass `source_type=None` to let `detect_format` infer it from the file
    extension. Pass an explicit value to force a particular routing (e.g.
    `SourceType.PDF_SLIDES` for a PDF that's actually a slide deck, or
    `SourceType.PDF_NOTES` for messy raw notes).
    """
    state: IndexingState = {
        "source_path": source_path,
        "language": None,
        "document": None,
        "blocks": [],
        "has_typographic_structure": False,
        "paragraphs": [],
        "hierarchy": None,
        "errors": [],
        "warnings": [],
    }
    if source_type is not None:
        state["source_type"] = source_type
    return state
