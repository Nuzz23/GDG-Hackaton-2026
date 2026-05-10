"""Audio parser — wraps `agent.asr.transcribe` and turns Whisper segments
into `Block`s with `TimeLocator`.

We rely on Whisper's built-in language detection (auto on the first ~30s).
The detected language is stored on each block's meta and surfaced to the
graph state via `parser_meta` so that `detect_language` can read it without
re-running detection.
"""

from __future__ import annotations

import logging
from pathlib import Path

from processing_agent.asr import transcribe
from processing_agent.models import Block, BlockKind, Document, SourceType, TimeLocator

logger = logging.getLogger(__name__)


def parse(path: str | Path) -> Document:
    p = Path(path)
    result = transcribe(str(p))
    blocks = [
        Block(
            id=seg.id,
            kind=BlockKind.UTTERANCE,
            text=seg.text,
            locator=TimeLocator(t_start=seg.t_start, t_end=seg.t_end),
            meta={"asr_lang": result.language, "asr_conf": result.language_probability},
        )
        for seg in result.segments
    ]
    if not blocks:
        raise ValueError(f"No speech detected in {p}.")
    return Document(
        source_path=str(p),
        source_type=SourceType.AUDIO,
        blocks=blocks,
        size_metric={"duration_seconds": result.duration_seconds},
        parser_meta={
            "extractor": "faster-whisper",
            "detected_language": result.language,
            "language_probability": result.language_probability,
        },
    )
