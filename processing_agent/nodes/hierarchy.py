"""Build the hierarchy from typographic structure (the structured branch).

For each format we know how to read the structural skeleton:

- MD: heading_level (1–6) on `BlockKind.HEADING` blocks.
- PPTX / PDF_SLIDES: each slide title opens a section; non-title blocks on
  the same slide become its paragraph children.
- PDF: heading detected by font size; heading depth is approximated by
  ranking unique heading font sizes (largest = level 1, etc.). This is
  imperfect but handles the common case of textbooks with 2–3 heading
  levels well.

The result is a `HierarchyNode` tree where:
  - leaves carry verbatim `text`,
  - internal nodes carry only `label` (left blank here; populated later by
    `label_nodes`),
  - every node's `locator` is the union of its descendants' locators.

We also produce `paragraphs` (the leaves as `SemanticParagraph`s) so the
state shape matches the semantic branch — downstream nodes don't need to
care which branch we came from.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from agent.models import (
    Block,
    BlockKind,
    HierarchyNode,
    NodeKind,
    SemanticParagraph,
    SourceLocator,
    SourceType,
    union_locators,
)
from agent.state import IndexingState

logger = logging.getLogger(__name__)


def build_hierarchy_from_structure(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    src = state.get("source_type")
    blocks = state["blocks"]

    if src == SourceType.MD:
        tree, paragraphs = _build_md(blocks)
    elif src in (SourceType.PPTX, SourceType.PDF_SLIDES):
        tree, paragraphs = _build_slides(blocks)
    elif src in (SourceType.PDF, SourceType.PDF_NOTES):
        tree, paragraphs = _build_pdf(blocks)
    else:
        return {"errors": [f"build_hierarchy_from_structure called for unsupported {src}"]}

    # Headings sometimes appear without body (decorative title pages, false
    # positives from the font-size heuristic). Prune them: any internal node
    # left with zero children, and any leaf with empty text, is dropped.
    _prune_empty(tree)
    if not tree.children:
        return {"errors": ["Structured hierarchy is empty after pruning."]}

    return {"hierarchy": tree, "paragraphs": paragraphs}


# ---------------------------------------------------------------------------
# Markdown — heading_level drives depth
# ---------------------------------------------------------------------------


def _build_md(blocks: list[Block]) -> tuple[HierarchyNode, list[SemanticParagraph]]:
    # Walk blocks; whenever we see a heading, open a new node at the
    # corresponding depth. Body blocks accumulate into a leaf paragraph
    # under the current innermost section. The root locator is a placeholder
    # rewritten by `_seal(root)` once children are in place.
    root = HierarchyNode(
        node_id="root",
        level=0,
        kind=NodeKind.ROOT,
        locator=blocks[0].locator,
    )
    stack: list[HierarchyNode] = [root]
    pending_leaf_blocks: list[Block] = []
    paragraphs: list[SemanticParagraph] = []

    def flush_leaf():
        nonlocal pending_leaf_blocks
        if not pending_leaf_blocks:
            return
        leaf, para = _leaf_from_blocks(pending_leaf_blocks)
        stack[-1].children.append(leaf)
        paragraphs.append(para)
        pending_leaf_blocks = []

    for b in blocks:
        if b.kind == BlockKind.HEADING:
            flush_leaf()
            level = int(b.meta.get("heading_level", 1))
            # Pop until parent is at level-1
            while len(stack) > 1 and stack[-1].level >= level:
                _seal(stack.pop())
            kind = _md_kind_for_level(level)
            node = HierarchyNode(
                node_id=_new_id(stack[-1]),
                level=level,
                kind=kind,
                label=b.text.strip(),
                locator=b.locator,
            )
            stack[-1].children.append(node)
            stack.append(node)
        else:
            pending_leaf_blocks.append(b)

    flush_leaf()
    while len(stack) > 1:
        _seal(stack.pop())
    _seal(root)
    return root, paragraphs


def _md_kind_for_level(level: int) -> NodeKind:
    if level == 1:
        return NodeKind.CHAPTER
    if level == 2:
        return NodeKind.SECTION
    return NodeKind.SUBSECTION


# ---------------------------------------------------------------------------
# Slides (PPTX / PDF_SLIDES) — slide titles open sections
# ---------------------------------------------------------------------------


def _build_slides(blocks: list[Block]) -> tuple[HierarchyNode, list[SemanticParagraph]]:
    root = HierarchyNode(
        node_id="root", level=0, kind=NodeKind.ROOT,
        locator=blocks[0].locator,
    )
    paragraphs: list[SemanticParagraph] = []
    current_section: Optional[HierarchyNode] = None
    current_body: list[Block] = []

    def flush_body():
        nonlocal current_body
        if current_section and current_body:
            leaf, para = _leaf_from_blocks(current_body)
            current_section.children.append(leaf)
            paragraphs.append(para)
        current_body = []

    for b in blocks:
        if b.kind == BlockKind.SLIDE_TITLE:
            flush_body()
            if current_section is not None:
                _seal(current_section)
            current_section = HierarchyNode(
                node_id=_new_id(root),
                level=1,
                kind=NodeKind.SECTION,
                label=b.text.strip(),
                locator=b.locator,
            )
            root.children.append(current_section)
        else:
            current_body.append(b)

    flush_body()
    if current_section is not None:
        _seal(current_section)
    _seal(root)
    return root, paragraphs


# ---------------------------------------------------------------------------
# PDF — heading font size buckets drive depth
# ---------------------------------------------------------------------------


def _build_pdf(blocks: list[Block]) -> tuple[HierarchyNode, list[SemanticParagraph]]:
    headings = [b for b in blocks if b.kind == BlockKind.HEADING]
    sizes = sorted({round(float(h.meta.get("font_size", 0.0)), 1) for h in headings}, reverse=True)
    # Cap at 3 heading levels — beyond that the signal is rarely reliable.
    size_to_level = {s: i + 1 for i, s in enumerate(sizes[:3])}

    root = HierarchyNode(
        node_id="root", level=0, kind=NodeKind.ROOT,
        locator=blocks[0].locator,
    )
    stack: list[HierarchyNode] = [root]
    pending: list[Block] = []
    paragraphs: list[SemanticParagraph] = []

    def flush_leaf():
        nonlocal pending
        if not pending:
            return
        leaf, para = _leaf_from_blocks(pending)
        stack[-1].children.append(leaf)
        paragraphs.append(para)
        pending = []

    for b in blocks:
        if b.kind == BlockKind.HEADING:
            size = round(float(b.meta.get("font_size", 0.0)), 1)
            level = size_to_level.get(size)
            if level is None:
                # Heading-candidate at a size below our top-3 — treat as body.
                pending.append(b)
                continue
            flush_leaf()
            while len(stack) > 1 and stack[-1].level >= level:
                _seal(stack.pop())
            kind = _md_kind_for_level(level)
            node = HierarchyNode(
                node_id=_new_id(stack[-1]),
                level=level,
                kind=kind,
                label=b.text.strip(),
                locator=b.locator,
            )
            stack[-1].children.append(node)
            stack.append(node)
        else:
            pending.append(b)

    flush_leaf()
    while len(stack) > 1:
        _seal(stack.pop())
    _seal(root)
    return root, paragraphs


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _leaf_from_blocks(bs: list[Block]) -> tuple[HierarchyNode, SemanticParagraph]:
    """Turn a contiguous run of body blocks into a leaf + its SemanticParagraph."""
    text = "\n".join(b.text for b in bs).strip()
    locator = union_locators([b.locator for b in bs])
    para_id = f"p_{uuid4().hex[:10]}"
    para = SemanticParagraph(
        id=para_id, block_ids=[b.id for b in bs], text=text, locator=locator
    )
    leaf = HierarchyNode(
        node_id=para_id,
        level=99,  # rewritten by `decide_depth` once the tree shape is known
        kind=NodeKind.PARAGRAPH,
        text=text,
        locator=locator,
    )
    return leaf, para


def _seal(node: HierarchyNode) -> None:
    """Recompute the node's locator as the union of its children's locators.

    This is the bottom-up locator construction promised in the brief.
    Internal nodes' locators are NEVER computed any other way.
    """
    if not node.children:
        return
    node.locator = union_locators([c.locator for c in node.children])


def _prune_empty(node: HierarchyNode) -> None:
    """Drop empty descendants in-place.

    Removes:
      - leaf paragraphs with empty text,
      - internal nodes that have no children left after recursive pruning.

    The root may end up with zero children, which the caller should treat as
    a failure (no usable structure was extracted).
    """
    kept: list[HierarchyNode] = []
    for c in node.children:
        _prune_empty(c)
        if c.children:
            kept.append(c)
        elif c.kind == NodeKind.PARAGRAPH and (c.text or "").strip():
            kept.append(c)
        # else: drop
    node.children = kept


def _new_id(parent: HierarchyNode) -> str:
    """Mint a hierarchical, human-readable node id under `parent`.

    Caller must append the new node to `parent.children` immediately after
    calling this — the id is derived from the *next* child index.
    """
    n = len(parent.children) + 1
    if parent.node_id == "root":
        return f"n_{n}"
    return f"{parent.node_id}_{n}"
