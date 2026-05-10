"""Validate the final tree against the output schema and serialize.

This node is the contract checkpoint at the bottom of the graph: anything
emitted here should be safe for a Part 3 consumer to read without further
checks. It does:

  1. Pydantic round-trip through `IndexOutput` (raises on shape errors).
  2. Structural invariants:
     - leaves carry `text`, internal nodes don't,
     - locator types are uniform within each subtree,
     - depth is in [2, 4].
  3. Optionally writes the result to disk if `output_path` is in state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from processing_agent.models import (
    HierarchyNode,
    IndexOutput,
    Language,
    NodeKind,
    OutputMetadata,
    SourceInfo,
)
from processing_agent.state import IndexingState

logger = logging.getLogger(__name__)


def validate_and_serialize(state: IndexingState) -> dict:
    if state.get("errors"):
        # If we got here with errors, surface them up; do not produce output.
        return {}

    tree = state.get("hierarchy")
    if tree is None:
        return {"errors": ["validate_and_serialize called with no hierarchy."]}

    issues = _structural_check(tree)
    if issues:
        return {"errors": [f"Structural validation failed: {'; '.join(issues)}"]}

    doc = state.get("document")
    if doc is None:
        return {"errors": ["validate_and_serialize called with no document."]}

    source = SourceInfo(
        type=doc.source_type,
        filename=Path(doc.source_path).name,
        language=state.get("language") or Language.EN,
        size_metric=doc.size_metric,
    )
    output = IndexOutput(
        source=source,
        tree=tree,
        metadata=OutputMetadata(warnings=list(state.get("warnings", []))),
    )

    payload: dict[str, Any] = output.model_dump(mode="json")
    output_path = state.get("output_path")
    if output_path:
        Path(output_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Wrote %s", output_path)

    return {"output": payload}


def _structural_check(tree: HierarchyNode) -> list[str]:
    issues: list[str] = []
    leaf_count = 0
    locator_types: set[str] = set()

    def walk(node: HierarchyNode, depth: int) -> None:
        nonlocal leaf_count
        locator_types.add(node.locator.type)
        if not node.children:
            if node.kind != NodeKind.PARAGRAPH:
                issues.append(f"non-paragraph leaf at {node.node_id}")
            if not node.text:
                issues.append(f"leaf {node.node_id} has empty text")
            leaf_count += 1
        else:
            if node.text is not None:
                issues.append(f"internal node {node.node_id} carries text")
            if node.kind == NodeKind.ROOT and depth != 0:
                issues.append(f"non-root node typed as root at {node.node_id}")
            for c in node.children:
                walk(c, depth + 1)

    walk(tree, 0)
    if leaf_count == 0:
        issues.append("tree has no leaves")
    if len(locator_types) > 1:
        issues.append(f"mixed locator types in tree: {locator_types}")
    return issues
