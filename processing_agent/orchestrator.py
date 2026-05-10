"""Top-level entry points.

Two public functions, one for each mode of operation:

- `index_document(path)`         — single-file path → indexed JSON
- `aggregate_indices(folder)`    — folder of indexed JSONs → cross-doc tree
- `index_or_aggregate(path)`     — auto-dispatch by inspecting the path

These are what the FastAPI backend imports. Keep their signatures small
and stable — hard interface boundary.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from processing_agent.aggregator import aggregate_folder
from processing_agent.graph import build_graph
from processing_agent.models import SourceType
from processing_agent.state import initial_state

logger = logging.getLogger(__name__)


_compiled_graph = None


def _graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def index_document(
    path: str | Path,
    *,
    source_type: Optional[SourceType] = None,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Run the indexing pipeline on a single file.

    Parameters
    ----------
    path:
        Filesystem path to the source file.
    source_type:
        Optional override. If omitted, the graph will infer the type from
        the file extension. Use this to force `pdf_notes` (which routes to
        the semantic branch) on a PDF that lacks reliable typographic
        structure, or `pdf_slides` on a PDF deck.
    output_path:
        If given, the final `index.json` is written to this path. Either
        way, the payload is returned in-memory.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    state = initial_state(str(p), source_type)
    if output_path is not None:
        state["output_path"] = str(output_path)

    result = _graph().invoke(state)

    if result.get("errors"):
        joined = " | ".join(result["errors"])
        raise RuntimeError(f"Indexing failed: {joined}")

    payload = result.get("output")
    if payload is None:
        raise RuntimeError("Indexing finished but produced no output payload.")
    return payload


def aggregate_indices(
    folder: str | Path,
    *,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Aggregate every valid `index.json` under `folder` into one tree.

    Thin wrapper around `agent.aggregator.aggregate_folder` so the
    orchestrator stays the single import point for the backend.
    """
    return aggregate_folder(folder, output_path=output_path)


def index_or_aggregate(
    path: str | Path,
    *,
    source_type: Optional[SourceType] = None,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Dispatch on path type: directory → aggregate, file → index.

    The CLI uses this so the user can pass either kind of path uniformly.
    """
    p = Path(path)
    if p.is_dir():
        return aggregate_indices(p, output_path=output_path)
    return index_document(p, source_type=source_type, output_path=output_path)
