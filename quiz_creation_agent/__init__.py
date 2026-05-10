"""Quiz/flashcard/open-question generation agent — Part 3a of Learn Different.

Public API: `generate_quiz(...)` from `quiz_creation_agent.orchestrator`.
"""

from typing import TYPE_CHECKING, Any

__all__ = ["generate_quiz"]
__version__ = "0.1.0"


if TYPE_CHECKING:
    from quiz_creation_agent.orchestrator import generate_quiz  # noqa: F401


def __getattr__(name: str) -> Any:
    if name == "generate_quiz":
        from quiz_creation_agent.orchestrator import generate_quiz as _fn
        return _fn
    raise AttributeError(f"module 'quiz_creation_agent' has no attribute {name!r}")
