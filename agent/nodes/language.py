"""Language detection — format-agnostic node, downstream of parsing.

For audio/video, the parser already detected the language via Whisper and
stored it in `document.parser_meta`. We just promote it.

For text formats, we use `lingua-py` if available (high accuracy on short
text), or fall back to `langdetect` if not. The detector runs on a 4 KB
sample of the linearized blocks — enough to be confident without paying for
a full document scan.
"""

from __future__ import annotations

import logging

from agent.models import Language
from agent.state import IndexingState

logger = logging.getLogger(__name__)


_SAMPLE_CHARS = 4096


def detect_language(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    doc = state.get("document")
    if doc is None:
        return {"errors": ["detect_language called before parsing."]}

    # Audio / video: use the language Whisper already detected.
    detected = doc.parser_meta.get("detected_language")
    if detected:
        lang = _normalize(detected)
        if lang is None:
            return {
                "errors": [f"Detected language '{detected}' is not supported (it/en only)."]
            }
        return {"language": lang}

    # Text formats: detect from a sample of the linearized blocks.
    sample = _sample_text(state["blocks"])
    if not sample:
        return {"errors": ["No text available for language detection."]}
    code = _detect_text(sample)
    lang = _normalize(code)
    if lang is None:
        return {
            "errors": [f"Detected language '{code}' is not supported (it/en only)."]
        }
    return {"language": lang}


def _sample_text(blocks) -> str:
    out: list[str] = []
    total = 0
    for b in blocks:
        out.append(b.text)
        total += len(b.text)
        if total >= _SAMPLE_CHARS:
            break
    return "\n".join(out)[:_SAMPLE_CHARS]


def _detect_text(sample: str) -> str:
    """Return an ISO-639-1 code. Tries `lingua` first, falls back to `langdetect`."""
    try:
        from lingua import IsoCode639_1, Language as LinguaLanguage, LanguageDetectorBuilder  # type: ignore

        detector = (
            LanguageDetectorBuilder.from_languages(
                LinguaLanguage.ITALIAN, LinguaLanguage.ENGLISH
            )
            .with_preloaded_language_models()
            .build()
        )
        detected = detector.detect_language_of(sample)
        if detected is None:
            return "en"
        return detected.iso_code_639_1.name.lower()
    except ImportError:
        pass

    try:
        from langdetect import detect  # type: ignore

        return detect(sample)
    except ImportError:
        logger.warning(
            "Neither `lingua` nor `langdetect` is installed; defaulting to 'en'."
        )
        return "en"


def _normalize(code: str) -> Language | None:
    code = (code or "").lower()
    if code in ("it", "ita", "italian"):
        return Language.IT
    if code in ("en", "eng", "english"):
        return Language.EN
    return None
