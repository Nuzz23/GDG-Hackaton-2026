"""PDF parser, with optional slide-mode.

We use PyMuPDF (`fitz`) — fastest mainstream extractor, gives per-span font
metadata, and produces character offsets we can map to `char_range`.

The parser produces blocks of three kinds:
  - `HEADING` when a span uses a font notably larger than the page median
    (multi-pass: we estimate the body font size first, then promote).
  - `LIST_ITEM` when a paragraph starts with a bullet-like prefix.
  - `PARAGRAPH` for everything else.

We DO NOT do OCR. If a page yields no text, we emit a warning. If the entire
document yields no text, the caller should fail loud — see
`agent.nodes.routing.ensure_blocks_or_fail`.

Slide PDFs (a deck exported as PDF) are routed here too, but with
`slide_mode=True`: each page becomes one slide, and we emit `SLIDE_TITLE`
plus `SLIDE_BODY` blocks instead of paragraphs.
"""

from __future__ import annotations

import logging
import statistics
from pathlib import Path
from typing import Iterable

from processing_agent.models import Block, BlockKind, Document, PDFLocator, SlideLocator, SourceType

logger = logging.getLogger(__name__)


# A heading is a span whose font size is at least this multiple of the
# document's median body font size. Tuned empirically; tweak in QA.
HEADING_FONT_RATIO = 1.18

# A bullet-like prefix in the first 4 chars of a line — narrow and conservative.
_BULLETS = ("•", "·", "-", "*", "▪", "◦", "■", "●")


def parse(path: str | Path, *, slide_mode: bool = False) -> Document:
    try:
        import fitz  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF is not installed. Install with `pip install pymupdf`."
        ) from e

    p = Path(path)
    doc = fitz.open(str(p))
    try:
        if slide_mode:
            blocks = list(_parse_slide_mode(doc))
            source_type = SourceType.PDF_SLIDES
            size_metric = {"slides": doc.page_count}
        else:
            blocks = list(_parse_text_mode(doc))
            source_type = SourceType.PDF
            size_metric = {"pages": doc.page_count}
    finally:
        doc.close()

    if not blocks:
        # No extractable text layer — likely a scanned PDF. Caller decides
        # whether to fail loud (we recommend it: OCR is out of scope).
        raise ValueError(
            f"No extractable text found in {p}. The PDF may be scanned. "
            "OCR is out of scope for this agent."
        )

    return Document(
        source_path=str(p),
        source_type=source_type,
        blocks=blocks,
        size_metric=size_metric,
        parser_meta={"extractor": "pymupdf", "slide_mode": slide_mode},
    )


# ---------------------------------------------------------------------------
# Text mode — books / lecture notes / dispense
# ---------------------------------------------------------------------------


def _parse_text_mode(doc) -> Iterable[Block]:
    body_font_size = _estimate_body_font_size(doc)
    heading_threshold = body_font_size * HEADING_FONT_RATIO

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        page_dict = page.get_text("dict")
        page_char_cursor = 0  # intra-page; the locator's page_start anchors it
        for block_dict in page_dict.get("blocks", []):
            if block_dict.get("type") != 0:  # skip image blocks
                continue
            for line in block_dict.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(s.get("text", "") for s in spans).strip()
                if not line_text:
                    continue
                max_font = max(s.get("size", 0.0) for s in spans)
                kind = _classify_line(line_text, max_font, heading_threshold)
                start = page_char_cursor
                end = page_char_cursor + len(line_text)
                page_char_cursor = end + 1  # +1 for the implicit newline
                bbox = block_dict.get("bbox")
                yield Block(
                    kind=kind,
                    text=line_text,
                    locator=PDFLocator(
                        page_start=page_idx + 1,
                        page_end=page_idx + 1,
                        char_range=(start, end),
                        bbox=tuple(bbox) if bbox else None,
                    ),
                    meta={
                        "font_size": max_font,
                        "is_heading_candidate": max_font >= heading_threshold,
                    },
                )


def _classify_line(text: str, font_size: float, heading_threshold: float) -> BlockKind:
    if font_size >= heading_threshold and len(text) <= 120:
        return BlockKind.HEADING
    if text[:1] in _BULLETS or _looks_like_numbered_list(text):
        return BlockKind.LIST_ITEM
    return BlockKind.PARAGRAPH


def _looks_like_numbered_list(text: str) -> bool:
    # "1. ", "1) ", "a) ", "i. " — narrow rule, tolerates a single space after.
    if len(text) < 3:
        return False
    head = text[:4]
    if head[0].isdigit() and head[1] in (".", ")") and head[2] == " ":
        return True
    if head[0].isalpha() and head[1] == ")" and head[2] == " ":
        return True
    return False


def _estimate_body_font_size(doc) -> float:
    """Estimate the document's median body font size.

    Sample up to the first ~20 pages to keep the cost bounded on long PDFs.
    Median is robust to outliers (titles, footnotes).
    """
    sizes: list[float] = []
    sample_pages = min(doc.page_count, 20)
    for page_idx in range(sample_pages):
        page_dict = doc[page_idx].get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size")
                    text = span.get("text", "").strip()
                    if size and text:
                        sizes.append(float(size))
    if not sizes:
        return 11.0  # safe default
    return statistics.median(sizes)


# ---------------------------------------------------------------------------
# Slide mode — a deck exported as PDF
# ---------------------------------------------------------------------------


def _parse_slide_mode(doc) -> Iterable[Block]:
    body_font_size = _estimate_body_font_size(doc)
    title_threshold = body_font_size * HEADING_FONT_RATIO

    for slide_idx in range(doc.page_count):
        page = doc[slide_idx]
        page_dict = page.get_text("dict")
        spans_with_meta: list[tuple[str, float]] = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        spans_with_meta.append((text, float(span.get("size", 0.0))))
        if not spans_with_meta:
            continue

        # Heuristic: the largest-font span at the top of the page is the title.
        max_size = max(s[1] for s in spans_with_meta)
        title_emitted = False
        for text, size in spans_with_meta:
            if not title_emitted and size >= max(title_threshold, max_size - 0.5):
                kind = BlockKind.SLIDE_TITLE
                title_emitted = True
            elif text[:1] in _BULLETS:
                kind = BlockKind.SLIDE_BULLET
            else:
                kind = BlockKind.SLIDE_BODY
            yield Block(
                kind=kind,
                text=text,
                locator=SlideLocator(
                    slide_index_start=slide_idx + 1,
                    slide_index_end=slide_idx + 1,
                ),
                meta={"font_size": size},
            )
