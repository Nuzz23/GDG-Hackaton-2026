"""Top-level entry point for the quiz generator.

Public API: `generate_quiz(...)` — what the CLI and the future eval agent /
backend will call. Stable signature, JSON-serializable return.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from quiz_creation_agent.extractor import extract
from quiz_creation_agent.generator import generate_items
from quiz_creation_agent.models import Difficulty, ItemType, SourceRef

logger = logging.getLogger(__name__)


def generate_quiz(
    input_path: str | Path,
    *,
    item_type: ItemType,
    n: int,
    difficulty: Difficulty = Difficulty.MEDIO,
    node_id: Optional[str] = None,
    language: Optional[str] = None,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Generate `n` items of `item_type` from `input_path`.

    Parameters
    ----------
    input_path:
        `.txt` / `.md` file (raw text) OR `.json` with the indexing-agent
        schema (paired with `node_id`).
    item_type:
        ItemType.FLASHCARD, ItemType.MCQ, or ItemType.OPEN_QUESTION.
    n:
        How many items to generate. Capped at MAX_N inside the generator.
    difficulty:
        Difficulty.FACILE / MEDIO / DIFFICILE. Default MEDIO.
    node_id:
        Required when `input_path` is an indexing-agent JSON; ignored otherwise.
    language:
        "it" or "en". If None, inferred from the index.json `source.language`
        when available, or detected from the text via `lingua-py`, or
        defaults to "it".
    output_path:
        If given, writes the JSON payload to that path.
    """
    text, source = extract(input_path, node_id=node_id)
    lang = language or _resolve_language(input_path, source, text)

    output = generate_items(
        text=text,
        item_type=item_type,
        n=n,
        difficulty=difficulty,
        language=lang,
        source=source,
    )

    payload = output.model_dump(mode="json")
    if output_path:
        Path(output_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        logger.info("Wrote %s", output_path)
    return payload


# ---------------------------------------------------------------------------
# Language resolution
# ---------------------------------------------------------------------------


def _resolve_language(input_path, source: SourceRef, text: str) -> str:
    p = Path(input_path)
    if p.suffix.lower() == ".json":
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            lang = raw.get("source", {}).get("language")
            if lang in ("it", "en"):
                return lang
        except Exception:
            pass
    return _detect_lang(text)


def _detect_lang(text: str) -> str:
    sample = text[:4096]
    try:
        from lingua import Language as LinguaLanguage, LanguageDetectorBuilder  # type: ignore

        detector = (
            LanguageDetectorBuilder.from_languages(
                LinguaLanguage.ITALIAN, LinguaLanguage.ENGLISH
            )
            .with_preloaded_language_models()
            .build()
        )
        d = detector.detect_language_of(sample)
        if d is None:
            return "it"
        return d.iso_code_639_1.name.lower()
    except ImportError:
        pass
    try:
        from langdetect import detect  # type: ignore

        code = detect(sample)
        return "en" if code == "en" else "it"
    except Exception:
        return "it"
