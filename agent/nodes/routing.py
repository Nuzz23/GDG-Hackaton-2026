"""Routing nodes and conditional-edge selectors.

Two routing decisions in the graph:

1. Format dispatch — at entry, pick the parser based on file extension.
   Resolved via the `route_parser` selector function used by an edge from
   `detect_format`.
2. Structure branch — after `detect_typographic_structure`, pick between
   `build_hierarchy_from_structure` and `semantic_segmentation`. Resolved
   via the `route_structure_branch` selector.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent.models import Document, SourceType
from agent.parsers import parse_audio, parse_md, parse_pdf, parse_pptx, parse_video
from agent.state import IndexingState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Format detection — entry node
# ---------------------------------------------------------------------------


_EXT_TO_TYPE: dict[str, SourceType] = {
    ".pdf": SourceType.PDF,
    ".pptx": SourceType.PPTX,
    ".ppt": SourceType.PPTX,
    ".md": SourceType.MD,
    ".markdown": SourceType.MD,
    ".mp3": SourceType.AUDIO,
    ".wav": SourceType.AUDIO,
    ".m4a": SourceType.AUDIO,
    ".flac": SourceType.AUDIO,
    ".ogg": SourceType.AUDIO,
    ".mp4": SourceType.VIDEO,
    ".mkv": SourceType.VIDEO,
    ".mov": SourceType.VIDEO,
    ".webm": SourceType.VIDEO,
    ".avi": SourceType.VIDEO,
}


def detect_format(state: IndexingState) -> dict:
    """Decide the source type from the file extension.

    Honours an already-set `source_type` if the caller forced one (e.g. the
    orchestrator wants to treat a PDF as `pdf_slides`). Otherwise falls back
    to extension-based detection.
    """
    if state.get("source_type"):
        return {}

    path = Path(state["source_path"])
    ext = path.suffix.lower()
    if ext not in _EXT_TO_TYPE:
        return {
            "errors": [f"Unsupported file extension: {ext}"],
        }
    return {"source_type": _EXT_TO_TYPE[ext]}


# ---------------------------------------------------------------------------
# Parser dispatch — selector for a conditional edge
# ---------------------------------------------------------------------------


def route_parser(state: IndexingState) -> str:
    """Return the name of the parser node to invoke."""
    if state.get("errors"):
        return "halt"
    st = state.get("source_type")
    if st in (SourceType.PDF, SourceType.PDF_NOTES):
        return "parse_pdf"
    if st == SourceType.PDF_SLIDES:
        return "parse_pdf_slides"
    if st == SourceType.PPTX:
        return "parse_pptx"
    if st == SourceType.MD:
        return "parse_md"
    if st == SourceType.AUDIO:
        return "parse_audio"
    if st == SourceType.VIDEO:
        return "parse_video"
    return "halt"


# ---------------------------------------------------------------------------
# Parser node functions — thin wrappers around `agent.parsers.*`
# ---------------------------------------------------------------------------


def _wrap_parse(fn, state: IndexingState, **kwargs) -> dict:
    try:
        doc: Document = fn(state["source_path"], **kwargs)
    except Exception as e:
        logger.exception("Parser failed")
        return {"errors": [f"Parsing failed: {e}"]}
    return {"document": doc, "blocks": list(doc.blocks)}


def parse_pdf_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_pdf, state)


def parse_pdf_slides_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_pdf, state, slide_mode=True)


def parse_pptx_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_pptx, state)


def parse_md_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_md, state)


def parse_audio_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_audio, state)


def parse_video_node(state: IndexingState) -> dict:
    return _wrap_parse(parse_video, state)


# ---------------------------------------------------------------------------
# Normalization — pass-through with sanity checks
# ---------------------------------------------------------------------------


def normalize_to_blocks(state: IndexingState) -> dict:
    """Promote `document.blocks` to top-level `blocks` and validate.

    Most parsers already populate `blocks` directly, but this node is the
    contract checkpoint after which the rest of the graph is format-agnostic.
    """
    if state.get("errors"):
        return {}
    doc = state.get("document")
    if doc is None or not doc.blocks:
        return {"errors": ["Parser produced no document or no blocks."]}
    return {"blocks": list(doc.blocks)}


# ---------------------------------------------------------------------------
# Structure branch selector
# ---------------------------------------------------------------------------


def route_structure_branch(state: IndexingState) -> str:
    if state.get("errors"):
        return "halt"
    return "structured" if state.get("has_typographic_structure") else "semantic"
