"""Detect whether the source has reliable typographic structure.

This is the most consequential routing decision in the graph: a wrong call
here pushes well-structured material into the LLM segmentation branch
(wasteful, lower quality) or unstructured material into the structural
branch (produces nothing useful).

Decision rules per source type:

- PPTX, PDF_SLIDES: trivially structured (slide titles).
- MD: structured iff at least one heading block.
- PDF: structured iff
    (a) at least N heading-candidate blocks (font ≥ 1.18× body), AND
    (b) heading_candidate_ratio is between 0.5% and 25% of total blocks
        (a textbook with sane heading density, not a book in all-caps).
- AUDIO, VIDEO: never structured — always go to the semantic branch.
- PDF_NOTES: same rules as PDF, but tighter (raw notes often have stray
  large fonts that aren't real headings).
"""

from __future__ import annotations

import logging

from processing_agent.models import BlockKind, SourceType
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


# Minimum number of heading-candidate blocks for a PDF to count as structured.
PDF_MIN_HEADINGS = 3
PDF_HEADING_RATIO_LO = 0.005
PDF_HEADING_RATIO_HI = 0.25


def detect_typographic_structure(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    src = state.get("source_type")
    blocks = state["blocks"]

    if src in (SourceType.AUDIO, SourceType.VIDEO):
        return {"has_typographic_structure": False}

    if src in (SourceType.PPTX, SourceType.PDF_SLIDES):
        # Slide titles act as the structural skeleton.
        has_titles = any(b.kind == BlockKind.SLIDE_TITLE for b in blocks)
        return {"has_typographic_structure": has_titles}

    if src == SourceType.MD:
        has_headings = any(b.kind == BlockKind.HEADING for b in blocks)
        return {"has_typographic_structure": has_headings}

    if src in (SourceType.PDF, SourceType.PDF_NOTES):
        heading_blocks = [b for b in blocks if b.kind == BlockKind.HEADING]
        ratio = len(heading_blocks) / max(len(blocks), 1)
        ok = (
            len(heading_blocks) >= PDF_MIN_HEADINGS
            and PDF_HEADING_RATIO_LO <= ratio <= PDF_HEADING_RATIO_HI
        )
        if not ok:
            logger.info(
                "PDF structure rejected: %d headings, ratio %.4f",
                len(heading_blocks),
                ratio,
            )
        return {"has_typographic_structure": ok}

    return {"has_typographic_structure": False}
