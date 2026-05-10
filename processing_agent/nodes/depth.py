"""Decide the final depth of the tree (2 to 4 levels) and renormalise levels.

This node is the guardrail against forcing a fixed hierarchy on heterogeneous
material. It does two things:

1. Computes the natural depth of the produced tree (max distance from root
   to a leaf).
2. Compresses or expands as needed so the result is between 2 and 4 levels,
   with leaves always at the deepest level.

Compression rule: if a chain of internal nodes has only one child at any
step, collapse it (we don't want skinny single-child branches that just
inflate the depth).

Expansion rule: we don't expand. If material is genuinely shallow (a slide
deck with 5 slides), the right answer is 2 levels, not 4 invented ones. The
brief is explicit about this.
"""

from __future__ import annotations

import logging
from typing import Iterable

from processing_agent.models import HierarchyNode, NodeKind
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


MIN_DEPTH = 2
MAX_DEPTH = 4


def decide_depth(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}
    tree = state.get("hierarchy")
    if tree is None:
        return {"errors": ["decide_depth called with no hierarchy."]}

    _collapse_single_child_chains(tree)
    _renormalise_levels(tree)

    natural_depth = _max_depth(tree)
    warnings: list[str] = []
    if natural_depth > MAX_DEPTH:
        # Flatten the deepest level into its parent.
        _flatten_to_depth(tree, MAX_DEPTH)
        warnings.append(
            f"natural depth {natural_depth} exceeded max ({MAX_DEPTH}); flattened"
        )
        _renormalise_levels(tree)

    return {"hierarchy": tree, "warnings": warnings} if warnings else {"hierarchy": tree}


def _max_depth(node: HierarchyNode) -> int:
    if not node.children:
        return 0
    return 1 + max(_max_depth(c) for c in node.children)


def _renormalise_levels(node: HierarchyNode, current: int = 0) -> None:
    node.level = current
    if not node.children:
        return
    for c in node.children:
        _renormalise_levels(c, current + 1)


def _collapse_single_child_chains(node: HierarchyNode) -> None:
    """Replace ``A -> B -> ...`` with ``A -> ...`` when B has a single sibling-less child.

    We collapse upward: B's sole child takes B's slot under A. Repeat until
    no more single-child internal chains. We never collapse a leaf into its
    parent (the leaf's `text` would be lost).
    """
    for c in node.children:
        _collapse_single_child_chains(c)

    new_children: list[HierarchyNode] = []
    for c in node.children:
        # Collapse only when c is internal AND has exactly one child AND that
        # child is also internal (or leaf — both safe since we keep the leaf).
        while (
            c.kind != NodeKind.PARAGRAPH
            and len(c.children) == 1
            and c.children[0].kind != NodeKind.PARAGRAPH
        ):
            c = c.children[0]
        new_children.append(c)
    node.children = new_children


def _flatten_to_depth(node: HierarchyNode, max_depth: int, depth: int = 0) -> None:
    """If the tree is deeper than max_depth, pull leaves up so they sit at max_depth."""
    if depth >= max_depth:
        # Replace this node's descendants with all leaves at or below it.
        node.children = list(_collect_leaves(node))
        return
    for c in node.children:
        _flatten_to_depth(c, max_depth, depth + 1)


def _collect_leaves(node: HierarchyNode) -> Iterable[HierarchyNode]:
    if not node.children:
        if node.kind == NodeKind.PARAGRAPH:
            yield node
        return
    for c in node.children:
        yield from _collect_leaves(c)
