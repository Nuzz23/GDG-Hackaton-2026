"""Generate short labels for internal nodes.

Two cases:

- Structured branch: internal node `label` is already the heading text from
  the source. We leave those untouched. They are accurate, traceable, and
  not creative.
- Semantic branch: internal nodes are unnamed (we only had id ranges). We
  ask the LLM to label them based on the verbatim text of their leaves.

We batch sections per LLM call. Leaves are NOT labeled — their `text` field
is the navigation surface, and adding a generated label there would inject
LLM-authored content into a position that should be source-only.
"""

from __future__ import annotations

import logging
from typing import Iterable

from agent.llm import call_json
from agent.models import HierarchyNode, Language, NodeKind
from agent.prompts import LABELING_SYSTEM, labeling_user_prompt
from agent.state import IndexingState

logger = logging.getLogger(__name__)


LABELING_BATCH = 16
LEAF_TEXT_PER_SECTION_CAP = 1200  # cap to keep prompts cheap


def label_nodes(state: IndexingState) -> dict:
    if state.get("errors"):
        return {}
    tree = state.get("hierarchy")
    language = state.get("language") or Language.EN
    if tree is None:
        return {"errors": ["label_nodes called with no hierarchy."]}

    unlabeled = [n for n in _internal_nodes(tree) if not n.label]
    if not unlabeled:
        return {}

    warnings: list[str] = []
    for batch in _batched(unlabeled, LABELING_BATCH):
        payload = [{"id": n.node_id, "text": _section_excerpt(n)} for n in batch]
        try:
            response = call_json(
                system=LABELING_SYSTEM,
                user=labeling_user_prompt(payload, language),
            )
        except Exception as e:
            logger.warning("Labeling batch failed: %s", e)
            warnings.append(f"labeling batch failed ({len(batch)} nodes)")
            for n in batch:
                n.label = _fallback_label(n)
            continue
        labels = response if isinstance(response, list) else []
        for n, lbl in zip(batch, labels):
            if isinstance(lbl, str) and lbl.strip():
                n.label = lbl.strip().rstrip(".").strip('"\'')
            else:
                n.label = _fallback_label(n)

    return {"hierarchy": tree, "warnings": warnings} if warnings else {"hierarchy": tree}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _internal_nodes(node: HierarchyNode) -> Iterable[HierarchyNode]:
    if node.children:
        if node.kind != NodeKind.ROOT:
            yield node
        for c in node.children:
            yield from _internal_nodes(c)


def _batched(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _section_excerpt(node: HierarchyNode) -> str:
    """Concatenate the first portion of leaf text under this node, capped."""
    pieces: list[str] = []
    used = 0
    for leaf in _collect_leaves(node):
        text = (leaf.text or "").strip()
        if not text:
            continue
        remaining = LEAF_TEXT_PER_SECTION_CAP - used
        if remaining <= 0:
            break
        pieces.append(text[:remaining])
        used += len(pieces[-1])
    return "\n".join(pieces)


def _collect_leaves(node: HierarchyNode) -> Iterable[HierarchyNode]:
    if not node.children:
        yield node
        return
    for c in node.children:
        yield from _collect_leaves(c)


def _fallback_label(node: HierarchyNode) -> str:
    excerpt = _section_excerpt(node).split()
    if not excerpt:
        return node.kind.value.capitalize()
    return " ".join(excerpt[:6])
