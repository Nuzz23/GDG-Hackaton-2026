"""Evaluation agent — Part 3b of the Learn Different track.

Public API: `evaluate(...)` from `eval_agent.orchestrator`. Lazy import.
"""

from typing import TYPE_CHECKING, Any

__all__ = ["evaluate"]
__version__ = "0.1.0"


if TYPE_CHECKING:
    from eval_agent.orchestrator import evaluate  # noqa: F401


def __getattr__(name: str) -> Any:
    if name == "evaluate":
        from eval_agent.orchestrator import evaluate as _fn
        return _fn
    raise AttributeError(f"module 'eval_agent' has no attribute {name!r}")
