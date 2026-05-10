"""Cleaning node.

Audio/video only — for textual sources this node is pass-through (the brief
forbids any rewriting of textual content; cleaning only applies to raw ASR
output).

Strategy: batch ASR segments in groups of `BATCH_SIZE` and ask the LLM to
return cleaned text for each segment ID, preserving IDs and ordering. We
NEVER pass the whole transcript as a blob — that breaks the segment ↔
timestamp mapping which is load-bearing for traceability.

If the LLM returns malformed JSON or drops IDs, we degrade gracefully: the
affected segments keep their original Whisper text. We log a warning rather
than failing the whole run.
"""

from __future__ import annotations

import logging

from processing_agent.llm import call_json
from processing_agent.models import Block, SourceType
from processing_agent.prompts import CLEANING_FEWSHOT, CLEANING_SYSTEM, cleaning_user_prompt
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


BATCH_SIZE = 12


def clean_blocks(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    src_type = state.get("source_type")
    if src_type not in (SourceType.AUDIO, SourceType.VIDEO):
        # Textual sources: explicit pass-through. The brief forbids rewriting.
        return {}

    blocks: list[Block] = state["blocks"]
    if not blocks:
        return {}

    cleaned_text_by_id: dict[str, str] = {}
    warnings: list[str] = []

    for batch in _batched(blocks, BATCH_SIZE):
        payload = [{"id": b.id, "text": b.text} for b in batch]
        try:
            response = call_json(
                system=CLEANING_SYSTEM,
                user=cleaning_user_prompt(payload),
                fewshot=CLEANING_FEWSHOT,
            )
        except Exception as e:
            logger.warning("Cleaning batch failed: %s", e)
            warnings.append(f"cleaning batch failed ({len(batch)} segments) — kept raw")
            continue
        if not isinstance(response, list):
            warnings.append("cleaning returned non-list response — kept raw")
            continue
        for item in response:
            if not isinstance(item, dict):
                continue
            sid = item.get("id")
            txt = item.get("text")
            if isinstance(sid, str) and isinstance(txt, str):
                cleaned_text_by_id[sid] = txt.strip()

    if not cleaned_text_by_id:
        return {"warnings": warnings} if warnings else {}

    new_blocks = [
        b.model_copy(update={"text": cleaned_text_by_id.get(b.id, b.text)})
        for b in blocks
    ]
    return {
        "blocks": new_blocks,
        "warnings": warnings,
    }


def _batched(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]
