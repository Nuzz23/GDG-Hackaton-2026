"""Cross-document aggregator.

Takes a folder containing one or more `index.json` files (output of the
per-document agent) and produces a single aggregate index that organizes
their sections into a navigable tree.

Design constraints:

- Only chapter/section nodes from each source are surfaced as refs.
  Subsections and leaf paragraphs are NOT propagated — the aggregate is a
  high-level navigation surface, not a duplicate of the per-document indices.
- The aggregate's leaves carry references (`DocumentRef`) back to specific
  (doc_id, node_id) pairs in the source documents. They never carry source
  text — the per-document `index.json` remains the source of truth for
  content.
- A single LLM call produces the whole structure, to keep API quota usage
  predictable. The prompt asks for organizing principle + tree in one shot.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import uuid4

from pydantic import ValidationError

from agent.aggregate_models import (
    AggregateMetadata,
    AggregateNode,
    AggregateNodeKind,
    AggregateOutput,
    DocumentRef,
    OrganizingPrinciple,
    SourceSummary,
)
from agent.llm import call_json
from agent.models import IndexOutput
from agent.prompts import (
    AGGREGATION_FEWSHOT,
    AGGREGATION_SYSTEM,
    aggregation_user_prompt,
)

logger = logging.getLogger(__name__)


# Only these `kind` values are surfaced as refs to the LLM. Subsection and
# paragraph are deliberately excluded — see module docstring.
_REF_KINDS = ("chapter", "section")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def aggregate_folder(
    folder: str | Path,
    *,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Aggregate every valid `*.json` index in `folder` into one tree.

    Returns the JSON-serializable payload. If `output_path` is given, the
    payload is also written to disk.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"{folder} is not a directory")

    indices = list(_load_valid_indices(folder))
    if not indices:
        raise ValueError(
            f"No valid indexing-agent JSON files found in {folder}. "
            f"Expected files matching the IndexOutput schema."
        )
    logger.info("Loaded %d valid index files", len(indices))

    sources = [_source_summary(idx) for idx in indices]
    refs = list(_collect_refs(indices))
    if not refs:
        raise ValueError(
            "No chapter/section nodes found across the loaded documents. "
            "Nothing to aggregate."
        )
    logger.info("Collected %d refs across %d sources", len(refs), len(sources))

    # Single LLM call: organizing principle + tree in one go. Wrap in
    # try/except so quota exhaustion or any transient API failure falls back
    # to the structural-by-source aggregate rather than crashing the run.
    warnings: list[str] = []
    try:
        response = call_json(
            system=AGGREGATION_SYSTEM,
            user=aggregation_user_prompt(_llm_sources(sources), _llm_refs(refs)),
            fewshot=AGGREGATION_FEWSHOT,
        )
    except Exception as e:  # noqa: BLE001 — we want every failure mode here
        msg = str(e).splitlines()[0][:200]
        logger.warning("Aggregation LLM call failed: %s", msg)
        warnings.append(f"aggregation LLM unavailable ({msg}); used fallback")
        aggregate = _fallback_aggregate(sources, refs, warnings)
    else:
        aggregate, build_warnings = _build_aggregate(response, sources, refs)
        warnings.extend(build_warnings)

    payload = aggregate.model_dump(mode="json")
    if output_path:
        Path(output_path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Wrote %s", output_path)
    return payload


# ---------------------------------------------------------------------------
# Loading & extraction
# ---------------------------------------------------------------------------


def _load_valid_indices(folder: Path) -> Iterable[IndexOutput]:
    """Yield every `*.json` in `folder` that validates as `IndexOutput`."""
    for path in sorted(folder.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("Skipping %s: not valid JSON (%s)", path.name, e)
            continue
        try:
            yield IndexOutput.model_validate(raw)
        except ValidationError as e:
            logger.warning(
                "Skipping %s: does not match IndexOutput schema (%s)",
                path.name, str(e).splitlines()[0],
            )


def _source_summary(idx: IndexOutput) -> SourceSummary:
    return SourceSummary(
        doc_id=idx.doc_id,
        filename=idx.source.filename,
        language=idx.source.language.value,
        size_metric=idx.source.size_metric,
    )


def _collect_refs(indices: list[IndexOutput]) -> Iterable[dict]:
    """Walk every doc tree, yielding a flat list of section-level refs."""
    for idx in indices:
        for ref in _walk_for_refs(
            idx.tree.model_dump(mode="json"),
            doc_id=idx.doc_id,
            filename=idx.source.filename,
            parent_label=None,
        ):
            yield ref


def _walk_for_refs(
    node: dict, *, doc_id: str, filename: str, parent_label: Optional[str]
) -> Iterable[dict]:
    """Yield refs for chapter/section nodes only.

    We DO recurse past chapters into their child sections (both are valid
    refs), but we stop at subsections and below — those don't reach the
    aggregate.
    """
    kind = node.get("kind")
    if kind == "root":
        for c in node.get("children", []):
            yield from _walk_for_refs(c, doc_id=doc_id, filename=filename, parent_label=None)
        return

    if kind in _REF_KINDS:
        yield {
            "ref_id": f"{doc_id}::{node['node_id']}",
            "doc_id": doc_id,
            "node_id": node["node_id"],
            "source_filename": filename,
            "kind": kind,
            "level": node.get("level", 1),
            "label": node.get("label") or "",
            "parent_label": parent_label,
        }
        # Recurse into children to surface nested sections (chapter -> section).
        for c in node.get("children", []):
            yield from _walk_for_refs(
                c, doc_id=doc_id, filename=filename, parent_label=node.get("label"),
            )
        return

    # Subsection / paragraph: stop, don't yield, don't recurse further.
    return


# ---------------------------------------------------------------------------
# LLM payload trimming
# ---------------------------------------------------------------------------


def _llm_sources(sources: list[SourceSummary]) -> list[dict]:
    """Compact source list passed to the LLM."""
    return [
        {
            "doc_id": s.doc_id,
            "filename": s.filename,
            "language": s.language,
        }
        for s in sources
    ]


def _llm_refs(refs: list[dict]) -> list[dict]:
    """Compact ref list passed to the LLM. Keep just what the LLM needs."""
    out = []
    for r in refs:
        item = {
            "ref_id": r["ref_id"],
            "kind": r["kind"],
            "level": r["level"],
            "label": r["label"],
        }
        if r.get("parent_label"):
            item["parent_label"] = r["parent_label"]
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Response → AggregateOutput
# ---------------------------------------------------------------------------


def _build_aggregate(
    response: Any,
    sources: list[SourceSummary],
    refs: list[dict],
) -> tuple[AggregateOutput, list[str]]:
    """Validate and turn the LLM response into a Pydantic AggregateOutput.

    Defensive: warns and falls back to a "Unsorted" group rather than raising
    when the LLM drops or invents refs. We never raise from quality issues —
    the call already cost API budget.
    """
    warnings: list[str] = []
    refs_by_id = {r["ref_id"]: r for r in refs}

    if not isinstance(response, dict):
        warnings.append("aggregator LLM returned non-object response; using fallback")
        return _fallback_aggregate(sources, refs, warnings), warnings

    principle_str = str(response.get("organizing_principle", "topical")).lower()
    try:
        principle = OrganizingPrinciple(principle_str)
    except ValueError:
        warnings.append(
            f"unknown organizing_principle '{principle_str}'; defaulting to topical"
        )
        principle = OrganizingPrinciple.TOPICAL

    rationale = str(response.get("principle_rationale", "")).strip() or "(no rationale provided)"

    raw_tree = response.get("tree")
    if not isinstance(raw_tree, list) or not raw_tree:
        warnings.append("aggregator returned empty tree; using fallback")
        return _fallback_aggregate(sources, refs, warnings), warnings

    seen: set[str] = set()
    root = AggregateNode(
        node_id="root", level=0, kind=AggregateNodeKind.ROOT, label=None,
    )
    for i, item in enumerate(raw_tree, start=1):
        node = _build_node(item, parent_id="root", index=i, refs_by_id=refs_by_id, seen=seen, depth=1)
        if node is not None:
            root.children.append(node)

    # Catch refs the LLM dropped: append under "Senza categoria".
    missing = [rid for rid in refs_by_id.keys() if rid not in seen]
    if missing:
        warnings.append(f"aggregator dropped {len(missing)} refs; appended to 'Senza categoria'")
        catch_all = AggregateNode(
            node_id=f"root_{len(root.children) + 1}",
            level=1,
            kind=AggregateNodeKind.CATEGORY,
            label="Senza categoria",
        )
        for j, rid in enumerate(missing, start=1):
            r = refs_by_id[rid]
            catch_all.children.append(_make_ref_leaf(
                node_id=f"{catch_all.node_id}_{j}",
                level=2,
                ref_data=r,
                display_label=r["label"],
            ))
        root.children.append(catch_all)

    aggregate = AggregateOutput(
        organizing_principle=principle,
        principle_rationale=rationale,
        sources=sources,
        tree=root,
        metadata=AggregateMetadata(
            warnings=warnings,
            n_sources=len(sources),
            n_refs=len(refs),
        ),
    )
    return aggregate, warnings


def _build_node(
    item: Any,
    *,
    parent_id: str,
    index: int,
    refs_by_id: dict[str, dict],
    seen: set[str],
    depth: int,
) -> Optional[AggregateNode]:
    """Recursively build an `AggregateNode` from an LLM tree item."""
    if not isinstance(item, dict):
        return None

    label = str(item.get("label") or "").strip()
    node_id = (
        f"agg_{index}" if parent_id == "root" else f"{parent_id}_{index}"
    )

    # Leaf ref?
    ref_id = item.get("ref_id")
    if isinstance(ref_id, str) and ref_id:
        if ref_id in seen:
            return None  # duplicate — drop silently, the missing-pass will cover orphans
        ref_data = refs_by_id.get(ref_id)
        if ref_data is None:
            return None  # invented ref_id — drop, the missing-pass will rebuild orphans
        seen.add(ref_id)
        return _make_ref_leaf(
            node_id=node_id,
            level=depth,
            ref_data=ref_data,
            display_label=label or ref_data["label"],
        )

    # Otherwise: category. Recurse into children.
    raw_children = item.get("children")
    if not isinstance(raw_children, list) or not raw_children:
        # Empty category — drop, don't keep dead branches.
        return None

    kind = AggregateNodeKind.CATEGORY if depth == 1 else AggregateNodeKind.SUBCATEGORY
    cat = AggregateNode(
        node_id=node_id, level=depth, kind=kind, label=label or f"Categoria {index}",
    )
    for j, child in enumerate(raw_children, start=1):
        built = _build_node(
            child, parent_id=node_id, index=j,
            refs_by_id=refs_by_id, seen=seen, depth=depth + 1,
        )
        if built is not None:
            cat.children.append(built)
    if not cat.children:
        return None
    return cat


def _make_ref_leaf(
    *,
    node_id: str,
    level: int,
    ref_data: dict,
    display_label: str,
) -> AggregateNode:
    return AggregateNode(
        node_id=node_id,
        level=level,
        kind=AggregateNodeKind.REF,
        label=display_label.strip(),
        ref=DocumentRef(
            doc_id=ref_data["doc_id"],
            node_id=ref_data["node_id"],
            source_filename=ref_data["source_filename"],
            source_label=ref_data["label"],
            source_kind=ref_data["kind"],
        ),
    )


def _fallback_aggregate(
    sources: list[SourceSummary],
    refs: list[dict],
    warnings: list[str],
) -> AggregateOutput:
    """Build a minimal aggregate when the LLM response is unusable.

    Groups refs by source filename. Always succeeds, never empty.
    """
    by_doc: dict[str, list[dict]] = {}
    for r in refs:
        by_doc.setdefault(r["source_filename"], []).append(r)

    root = AggregateNode(
        node_id="root", level=0, kind=AggregateNodeKind.ROOT, label=None,
    )
    for i, (filename, rs) in enumerate(by_doc.items(), start=1):
        cat = AggregateNode(
            node_id=f"agg_{i}", level=1, kind=AggregateNodeKind.CATEGORY,
            label=Path(filename).stem,
        )
        for j, r in enumerate(rs, start=1):
            cat.children.append(_make_ref_leaf(
                node_id=f"{cat.node_id}_{j}", level=2,
                ref_data=r, display_label=r["label"],
            ))
        root.children.append(cat)

    return AggregateOutput(
        organizing_principle=OrganizingPrinciple.STRUCTURAL,
        principle_rationale="Fallback: aggregator LLM unavailable, grouped by source filename.",
        sources=sources,
        tree=root,
        metadata=AggregateMetadata(
            warnings=warnings,
            n_sources=len(sources),
            n_refs=len(refs),
        ),
    )
