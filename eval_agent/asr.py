"""ASR wrapper around `faster-whisper` for the evaluation agent.

Diverges from `processing_agent/asr.py` in one important way: it requests
**word-level timestamps** by default. The eval agent's paralinguistic
feature extractor (Phase 4) needs those timestamps to compute pause
statistics, intra-segment hesitations, and self-correction patterns at
sub-segment resolution. The indexing agent doesn't need them.

Returns segments WITH a `words` list (each with `start`, `end`, `word`,
`probability`). Segment-level fields (`t_start`, `t_end`, `text`) remain
identical to the indexing-agent shape so that any code that just wants the
transcript continues to work.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


DEFAULT_MODEL_SIZE = os.environ.get("AGENT_WHISPER_MODEL", "medium")
DEFAULT_DEVICE = os.environ.get("AGENT_WHISPER_DEVICE", "auto")
DEFAULT_COMPUTE_TYPE = os.environ.get("AGENT_WHISPER_COMPUTE", "auto")


def _vad_default() -> bool:
    """Resolve the VAD default at call time, not import time.

    VAD filtering removes long silences before transcription. Helpful for
    lecture audio (the agent's primary use case) — speeds things up and
    reduces hallucination on quiet stretches. But for material with a
    music bed under voice (sung audio, podcasts with intro music) VAD
    can over-aggressively classify speech-with-music as silence and
    discard real content.

    Read on every call so the CLI's `--novad` flag (which sets the env
    var inside `main()`) takes effect even though `asr` was imported
    earlier.
    """
    return os.environ.get("AGENT_WHISPER_VAD", "true").strip().lower() not in (
        "0", "false", "no", "off",
    )


@dataclass
class TranscriptWord:
    start: float
    end: float
    word: str
    probability: float


@dataclass
class TranscriptSegment:
    id: str
    t_start: float
    t_end: float
    text: str
    words: list[TranscriptWord]


@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    language: str
    language_probability: float
    duration_seconds: float


_model = None


def _get_model(model_size: Optional[str] = None):
    """Return a process-wide WhisperModel, lazy-loaded.

    `faster-whisper` is imported lazily so that environments without the
    package can still import the rest of the agent (only the audio path
    breaks at call time, not at import).
    """
    global _model
    if _model is not None and model_size is None:
        return _model

    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper is not installed. Install with `pip install faster-whisper`."
        ) from e

    size = model_size or DEFAULT_MODEL_SIZE
    logger.info("Loading faster-whisper model: %s (device=%s, compute=%s)",
                size, DEFAULT_DEVICE, DEFAULT_COMPUTE_TYPE)
    model = WhisperModel(size, device=DEFAULT_DEVICE, compute_type=DEFAULT_COMPUTE_TYPE)
    if model_size is None:
        _model = model
    return model


def transcribe(
    audio_path: str,
    *,
    language: Optional[str] = None,
    model_size: Optional[str] = None,
    vad_filter: Optional[bool] = None,
) -> TranscriptionResult:
    """Transcribe an audio file with faster-whisper.

    `language=None` enables auto-detection on the first ~30 seconds.
    `vad_filter=None` reads the default from `AGENT_WHISPER_VAD` (true unless
    explicitly disabled). Pass an explicit boolean to override per-call.
    The returned segments carry per-segment timestamps suitable for our
    `TimeLocator`.
    """
    model = _get_model(model_size)
    use_vad = _vad_default() if vad_filter is None else vad_filter
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=use_vad,
        word_timestamps=True,
    )

    segments: list[TranscriptSegment] = []
    for i, seg in enumerate(segments_iter):
        words_raw = getattr(seg, "words", None) or []
        words = [
            TranscriptWord(
                start=float(w.start),
                end=float(w.end),
                word=w.word,
                probability=float(getattr(w, "probability", 0.0)),
            )
            for w in words_raw
        ]
        segments.append(
            TranscriptSegment(
                id=f"s_{i:05d}",
                t_start=float(seg.start),
                t_end=float(seg.end),
                text=seg.text.strip(),
                words=words,
            )
        )

    return TranscriptionResult(
        segments=segments,
        language=info.language,
        language_probability=float(info.language_probability),
        duration_seconds=float(info.duration),
    )
