"""Hierarchical clustering — bottom-up roll-up from semantic paragraphs to
sections (and optionally chapters for long material).

We do this in 1 or 2 passes depending on document size:
  - <= ~12 paragraphs: a single pass groups them into sections.
  - > ~12 paragraphs: two passes — paragraphs -> sections -> chapters.

Like segmentation, the LLM only returns id ranges. Labels for the resulting
internal nodes come later, in `label_nodes`.

The `decide_depth` node looks at the resulting tree shape and trims/expands
where appropriate — see `agent.nodes.depth`.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from processing_agent.llm import call_json
from processing_agent.models import (
    HierarchyNode,
    NodeKind,
    SemanticParagraph,
    union_locators,
)
from processing_agent.prompts import CLUSTERING_SYSTEM, clustering_user_prompt
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


SECTION_TARGET_MAX = 12
CHAPTER_TARGET_MAX = 8


def hierarchical_clustering(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}

    paragraphs: list[SemanticParagraph] = state.get("paragraphs", [])
    if not paragraphs:
        # Structured branch already populated `hierarchy`. Pass through.
        if state.get("hierarchy"):
            return {}
        return {"errors": ["hierarchical_clustering called with no paragraphs."]}

    # If the structured branch already built a tree, we're not in this branch.
    if state.get("hierarchy"):
        return {}

    # Step 1: paragraphs -> sections.
    leaves = [_paragraph_to_leaf(p) for p in paragraphs]
    sections = _cluster_one_pass(
        leaves, level=1, kind=NodeKind.SECTION, target_max=SECTION_TARGET_MAX
    )

    # Step 2: if many sections, sections -> chapters.
    if len(sections) > CHAPTER_TARGET_MAX:
        chapters = _cluster_one_pass(
            sections, level=1, kind=NodeKind.CHAPTER, target_max=CHAPTER_TARGET_MAX
        )
        # Re-level: chapters at 1, sections at 2, paragraphs at 3.
        for ch in chapters:
            for sec in ch.children:
                sec.level = 2
                sec.kind = NodeKind.SECTION
                for leaf in sec.children:
                    leaf.level = 3
        top = chapters
    else:
        for sec in sections:
            for leaf in sec.children:
                leaf.level = 2
        top = sections

    root = HierarchyNode(
        node_id="root",
        level=0,
        kind=NodeKind.ROOT,
        locator=top[0].locator,
    )
    for i, t in enumerate(top, start=1):
        t.node_id = f"n_{i}"
        _renumber(t)
        root.children.append(t)
    root.locator = union_locators([c.locator for c in root.children])
    return {"hierarchy": root}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paragraph_to_leaf(p: SemanticParagraph) -> HierarchyNode:
    return HierarchyNode(
        node_id=p.id,
        level=99,  # rewritten by decide_depth
        kind=NodeKind.PARAGRAPH,
        text=p.text,
        locator=p.locator,
    )


def _cluster_one_pass(
    children: list[HierarchyNode],
    *,
    level: int,
    kind: NodeKind,
    target_max: int,
) -> list[HierarchyNode]:
    """Ask the LLM to group `children` into contiguous parents."""
    if len(children) <= 1:
        # Wrap the single child in a parent so callers always get the level
        # they asked for.
        parent = HierarchyNode(
            node_id=f"tmp_{uuid4().hex[:8]}",
            level=level,
            kind=kind,
            locator=children[0].locator,
            children=list(children),
        )
        return [parent]

    payload = [
        {
            "id": c.node_id,
            "label": (c.label or _peek(c.text or "", 80)) if (c.label or c.text) else c.node_id,
        }
        for c in children
    ]
    try:
        response = call_json(
            system=CLUSTERING_SYSTEM,
            user=clustering_user_prompt(payload),
        )
    except Exception as e:
        logger.warning("Clustering LLM call failed: %s — falling back to chunks", e)
        response = _fallback_groups(children, target_max)

    ranges = _validate_ranges(response, children)
    return _ranges_to_parents(ranges, children, level=level, kind=kind)


def _peek(text: str, n: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _validate_ranges(response, children: list[HierarchyNode]) -> list[tuple[str, str]]:
    valid = {c.node_id for c in children}
    order = {c.node_id: i for i, c in enumerate(children)}
    out: list[tuple[str, str]] = []
    if not isinstance(response, list):
        return [(c.node_id, c.node_id) for c in children]
    for item in response:
        if not isinstance(item, dict):
            continue
        s = item.get("start_id")
        e = item.get("end_id")
        if not (isinstance(s, str) and isinstance(e, str)):
            continue
        if s not in valid or e not in valid:
            continue
        if order[s] > order[e]:
            continue
        out.append((s, e))
    if not out:
        return [(c.node_id, c.node_id) for c in children]
    return out


def _ranges_to_parents(
    ranges: list[tuple[str, str]],
    children: list[HierarchyNode],
    *,
    level: int,
    kind: NodeKind,
) -> list[HierarchyNode]:
    order = {c.node_id: i for i, c in enumerate(children)}
    seen: set[str] = set()
    parents: list[HierarchyNode] = []
    for s, e in sorted(ranges, key=lambda r: order[r[0]]):
        if s in seen:
            continue
        i_s, i_e = order[s], order[e]
        group = children[i_s : i_e + 1]
        if not group:
            continue
        for c in group:
            seen.add(c.node_id)
        parent = HierarchyNode(
            node_id=f"tmp_{uuid4().hex[:8]}",
            level=level,
            kind=kind,
            locator=union_locators([c.locator for c in group]),
            children=list(group),
        )
        parents.append(parent)
    return parents


def _fallback_groups(children: list[HierarchyNode], target_max: int) -> list[dict]:
    n = len(children)
    if n <= target_max:
        return [{"start_id": children[0].node_id, "end_id": children[-1].node_id}]
    chunk = max(1, n // target_max)
    out: list[dict] = []
    i = 0
    while i < n:
        j = min(n, i + chunk)
        out.append({"start_id": children[i].node_id, "end_id": children[j - 1].node_id})
        i = j
    return out


def _renumber(node: HierarchyNode, prefix: Optional[str] = None) -> None:
    """Replace temp ids with hierarchical ones once the tree is rooted."""
    base = prefix or node.node_id
    for i, child in enumerate(node.children, start=1):
        child.node_id = f"{base}_{i}"
        _renumber(child, child.node_id)
