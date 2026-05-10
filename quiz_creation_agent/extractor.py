"""Source extraction.

Two input modes, autodetected from the file extension:

- `.txt` / `.md`            → raw text file. The whole file becomes the source.
- `.json` (with `--node`)   → an `IndexOutput` produced by `processing_agent`.
                              We navigate to the node with the given id and
                              collect:
                                - if it's a leaf paragraph: its `text`.
                                - if it's a section / chapter / subsection:
                                  the concatenation of all leaf paragraphs
                                  in its subtree.

The function returns `(text, SourceRef)`. The SourceRef is fully populated
when input came from `index.json`, partially populated for raw text.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from quiz_creation_agent.models import SourceRef

logger = logging.getLogger(__name__)


_TEXT_SUFFIXES = (".txt", ".md", ".markdown")
_INDEX_SUFFIXES = (".json",)
_EXCERPT_CHARS = 240


def extract(input_path: str | Path, node_id: Optional[str] = None) -> tuple[str, SourceRef]:
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(p)

    suffix = p.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        return _extract_raw_text(p)
    if suffix in _INDEX_SUFFIXES:
        if not node_id:
            raise ValueError(
                f"{p.name} looks like an indexing-agent JSON; pass --node NODE_ID "
                "to point at the section/paragraph you want quizzes for."
            )
        return _extract_from_index(p, node_id)
    raise ValueError(
        f"Unsupported input extension {suffix!r}. Expected .txt, .md, or .json."
    )


# ---------------------------------------------------------------------------
# Raw text input
# ---------------------------------------------------------------------------


def _extract_raw_text(p: Path) -> tuple[str, SourceRef]:
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{p.name} is empty.")
    return text, SourceRef(
        source_filename=p.name,
        excerpt=_excerpt(text),
    )


# ---------------------------------------------------------------------------
# index.json input
# ---------------------------------------------------------------------------


def _extract_from_index(p: Path, node_id: str) -> tuple[str, SourceRef]:
    raw = json.loads(p.read_text(encoding="utf-8"))
    # Validate the bare minimum: this is an IndexOutput-shaped payload.
    if not isinstance(raw, dict) or "tree" not in raw or "source" not in raw:
        raise ValueError(
            f"{p.name} does not look like an indexing-agent JSON "
            "(missing 'tree' or 'source')."
        )

    node = _find_node(raw["tree"], node_id)
    if node is None:
        # Helpful: list a few real ids in the file to nudge the user.
        sample_ids = list(_iter_node_ids(raw["tree"]))[:8]
        raise ValueError(
            f"node_id {node_id!r} not found in {p.name}. "
            f"Available ids include: {sample_ids}"
        )

    text = _collect_text(node).strip()
    if not text:
        raise ValueError(f"node {node_id!r} has no text under it.")

    return text, SourceRef(
        source_filename=raw["source"]["filename"],
        excerpt=_excerpt(text),
        doc_id=raw.get("doc_id"),
        node_id=node["node_id"],
        source_label=node.get("label"),
        locator=node.get("locator"),
    )


def _find_node(node: dict, target_id: str) -> Optional[dict]:
    if node.get("node_id") == target_id:
        return node
    for c in node.get("children", []):
        found = _find_node(c, target_id)
        if found is not None:
            return found
    return None


def _collect_text(node: dict) -> str:
    """Return the concatenated text of every leaf descendant of `node`.

    For a leaf paragraph node the result is just its `text`. For an internal
    node the result is the joined text of all paragraph leaves, in document
    order.
    """
    if not node.get("children"):
        # Leaf paragraph (or a stray empty node)
        return node.get("text") or ""
    pieces: list[str] = []
    for c in node["children"]:
        sub = _collect_text(c)
        if sub:
            pieces.append(sub)
    return "\n\n".join(pieces)


def _iter_node_ids(node: dict):
    yield node.get("node_id")
    for c in node.get("children", []):
        yield from _iter_node_ids(c)


def _excerpt(text: str, n: int = _EXCERPT_CHARS) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"
