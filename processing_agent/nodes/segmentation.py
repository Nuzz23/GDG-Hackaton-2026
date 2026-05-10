"""Semantic segmentation — group blocks into semantic paragraphs.

Used when typographic structure is absent or unreliable: raw notes PDFs,
markdown without headings, audio/video transcripts.

Strategy: LLM-based, batched, ID-preserving. We never let the LLM produce
new text — it returns only `{start_id, end_id}` ranges over input block ids.
We then build the `SemanticParagraph`s by concatenating the verbatim text of
blocks in each range, and unioning their locators.

Why LLM over embedding-based: for a hackathon, an LLM with a strict prompt
is more controllable and easier to tune. Embedding-based TextTiling is more
elegant but needs careful threshold tuning per language and source type.
The state schema and graph wiring don't change between the two approaches —
we can swap implementations later without restructuring the agent.
"""

from __future__ import annotations

import logging
from typing import Optional

from processing_agent.llm import call_json
from processing_agent.models import Block, SemanticParagraph, union_locators
from processing_agent.prompts import (
    SEGMENTATION_FEWSHOT,
    SEGMENTATION_SYSTEM,
    segmentation_user_prompt,
)
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


# Soft cap on how many blocks we feed to the LLM per call. Larger batches
# preserve more context but cost more tokens and increase the chance of a
# malformed response. ~80 is the sweet spot for Gemini Flash on this task.
BATCH_BLOCKS = 80
# Overlap between batches so a topic shift near a batch boundary isn't lost.
BATCH_OVERLAP = 5


def semantic_segmentation(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    blocks: list[Block] = state["blocks"]
    if not blocks:
        return {"errors": ["semantic_segmentation called with no blocks."]}

    block_by_id = {b.id: b for b in blocks}

    all_ranges: list[tuple[str, str]] = []
    warnings: list[str] = []

    for batch in _windowed(blocks, BATCH_BLOCKS, BATCH_OVERLAP):
        payload = [{"id": b.id, "text": _truncate(b.text, 600)} for b in batch]
        try:
            response = call_json(
                system=SEGMENTATION_SYSTEM,
                user=segmentation_user_prompt(payload),
                fewshot=SEGMENTATION_FEWSHOT,
            )
        except Exception as e:
            logger.warning("Segmentation batch failed: %s — falling back to 1-block groups", e)
            warnings.append(f"segmentation batch failed ({len(batch)} blocks) — fallback")
            response = [{"start_id": b.id, "end_id": b.id} for b in batch]

        ranges = _validate_ranges(response, batch)
        all_ranges.extend(ranges)

    # Resolve overlap between batches: deduplicate ranges by start_id.
    seen_starts: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for s, e in all_ranges:
        if s in seen_starts:
            continue
        seen_starts.add(s)
        deduped.append((s, e))

    paragraphs = _ranges_to_paragraphs(deduped, blocks, block_by_id)
    if not paragraphs:
        return {"errors": ["Segmentation produced no paragraphs."]}
    return {"paragraphs": paragraphs, "warnings": warnings}


def _truncate(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _windowed(blocks: list[Block], size: int, overlap: int):
    if len(blocks) <= size:
        yield blocks
        return
    step = max(size - overlap, 1)
    i = 0
    while i < len(blocks):
        yield blocks[i : i + size]
        if i + size >= len(blocks):
            break
        i += step


def _validate_ranges(response, batch: list[Block]) -> list[tuple[str, str]]:
    """Defensive parse of LLM output. Drops malformed ranges; doesn't raise."""
    valid_ids = {b.id for b in batch}
    order = {b.id: i for i, b in enumerate(batch)}
    out: list[tuple[str, str]] = []
    if not isinstance(response, list):
        return [(b.id, b.id) for b in batch]
    for item in response:
        if not isinstance(item, dict):
            continue
        s = item.get("start_id")
        e = item.get("end_id")
        if not (isinstance(s, str) and isinstance(e, str)):
            continue
        if s not in valid_ids or e not in valid_ids:
            continue
        if order[s] > order[e]:
            continue
        out.append((s, e))
    if not out:
        return [(b.id, b.id) for b in batch]
    return out


def _ranges_to_paragraphs(
    ranges: list[tuple[str, str]],
    blocks: list[Block],
    block_by_id: dict[str, Block],
) -> list[SemanticParagraph]:
    order = {b.id: i for i, b in enumerate(blocks)}
    paragraphs: list[SemanticParagraph] = []
    for s, e in sorted(ranges, key=lambda r: order[r[0]]):
        i_s, i_e = order[s], order[e]
        run = blocks[i_s : i_e + 1]
        if not run:
            continue
        text = "\n".join(b.text for b in run).strip()
        locator = union_locators([b.locator for b in run])
        paragraphs.append(
            SemanticParagraph(
                block_ids=[b.id for b in run],
                text=text,
                locator=locator,
            )
        )
    return paragraphs
