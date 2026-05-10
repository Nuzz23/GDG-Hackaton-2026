"""Session state load/save.

Persists `SessionState` to `data/traces/<session_id>/_session.json`.
The same directory hosts per-event files (`<event_id>.json`), written by
the `emit_trace_event` node. The leading underscore on `_session.json`
keeps it visually grouped at the top of any directory listing.

This is the ONLY place the agent reads/writes session state. Nodes get
the loaded state via the LangGraph state and update it via mutations
that are then re-saved by `update_session_state`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from eval_agent.models import SessionState

logger = logging.getLogger(__name__)


DEFAULT_BASE = Path("data/traces")


def session_dir(session_id: str, base: Path = DEFAULT_BASE) -> Path:
    return base / session_id


def session_file(session_id: str, base: Path = DEFAULT_BASE) -> Path:
    return session_dir(session_id, base) / "_session.json"


def load_session(session_id: str, base: Path = DEFAULT_BASE) -> SessionState:
    """Load session state from disk, or return a fresh one if absent."""
    p = session_file(session_id, base)
    if p.exists():
        try:
            return SessionState.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(
                "Could not parse %s (%s); starting fresh session.", p, e
            )
    return SessionState(session_id=session_id)


def save_session(state: SessionState, base: Path = DEFAULT_BASE) -> None:
    p = session_file(state.session_id, base)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )
