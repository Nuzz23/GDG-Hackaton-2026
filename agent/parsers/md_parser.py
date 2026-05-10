"""Markdown parser — `markdown-it-py`.

Walks the markdown token stream and emits:
  - HEADING blocks for `# ... ######` (with `meta.heading_level` set so
    `build_hierarchy_from_structure` can use them directly).
  - LIST_ITEM for items inside `bullet_list` / `ordered_list`.
  - PARAGRAPH for everything else.

Character offsets are real: we use the source positions reported by the
parser's `map` field on each token to compute `char_offset_start/end`. This
means every block's `MarkdownLocator` points back to a real range in the
original file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from agent.models import Block, BlockKind, Document, MarkdownLocator, SourceType

logger = logging.getLogger(__name__)


def parse(path: str | Path) -> Document:
    try:
        from markdown_it import MarkdownIt  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "markdown-it-py is not installed. Install with `pip install markdown-it-py`."
        ) from e

    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    md = MarkdownIt("commonmark")
    tokens = md.parse(raw)
    blocks = list(_iter_blocks(tokens, raw))
    if not blocks:
        raise ValueError(f"No content found in {p}.")
    return Document(
        source_path=str(p),
        source_type=SourceType.MD,
        blocks=blocks,
        size_metric={"chars": len(raw)},
        parser_meta={"extractor": "markdown-it-py"},
    )


def _line_offsets(text: str) -> list[int]:
    """Return cumulative char offsets for the start of each line in `text`.

    `offsets[i]` is the index in `text` where line `i` starts. There's one
    extra trailing entry equal to len(text) + 1 so callers can index
    `offsets[line_end]` without bounds checks.
    """
    offsets = [0]
    cursor = 0
    for line in text.split("\n"):
        cursor += len(line) + 1
        offsets.append(cursor)
    return offsets


def _range_from_map(token_map, line_offsets: list[int], src_len: int) -> tuple[int, int]:
    if not token_map:
        return (0, src_len)
    line_start, line_end = token_map  # line_end is exclusive
    start = line_offsets[line_start] if line_start < len(line_offsets) else 0
    # Subtract trailing newline so the range hugs the content.
    end_idx = min(line_end, len(line_offsets) - 1)
    end = line_offsets[end_idx] - 1
    end = max(end, start)
    return (start, end)


def _iter_blocks(tokens, raw: str) -> Iterable[Block]:
    line_offsets = _line_offsets(raw)
    src_len = len(raw)
    in_list = False
    list_kind: str | None = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])  # 'h1' -> 1
            inline = tokens[i + 1]
            text = inline.content.strip()
            start, end = _range_from_map(tok.map, line_offsets, src_len)
            yield Block(
                kind=BlockKind.HEADING,
                text=text,
                locator=MarkdownLocator(
                    char_offset_start=start, char_offset_end=end
                ),
                meta={"heading_level": level},
            )
            # skip heading_open, inline, heading_close
            i += 3
            continue
        if tok.type in ("bullet_list_open", "ordered_list_open"):
            in_list = True
            list_kind = tok.type
            i += 1
            continue
        if tok.type in ("bullet_list_close", "ordered_list_close"):
            in_list = False
            list_kind = None
            i += 1
            continue
        if tok.type == "paragraph_open":
            inline = tokens[i + 1]
            text = inline.content.strip()
            if text:
                start, end = _range_from_map(tok.map, line_offsets, src_len)
                kind = BlockKind.LIST_ITEM if in_list else BlockKind.PARAGRAPH
                yield Block(
                    kind=kind,
                    text=text,
                    locator=MarkdownLocator(
                        char_offset_start=start, char_offset_end=end
                    ),
                    meta={"list_kind": list_kind} if in_list else {},
                )
            i += 3
            continue
        i += 1
