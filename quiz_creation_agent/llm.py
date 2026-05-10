"""LLM client wrapper.

Single entry point for every Gemini call in the agent. Centralising it here
means we get one place to:
  - configure the model name and temperature,
  - parse JSON safely (Gemini sometimes wraps output in ```json fences),
  - retry on transient failures,
  - swap providers in the future if needed.

We default to Gemini 2.5 Flash via `langchain-google-genai`. The team has
Google AI Studio access; a `GOOGLE_API_KEY` environment variable is expected.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Load a .env file at the project root if present. Cheap and silent if
# missing, lets the agent run from any subprocess (CLI, background tasks)
# without depending on the parent shell's environment.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


DEFAULT_MODEL = os.environ.get("AGENT_GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_TEMPERATURE = float(os.environ.get("AGENT_GEMINI_TEMPERATURE", "0.0"))


_client: Optional[ChatGoogleGenerativeAI] = None


def get_client(model: Optional[str] = None, temperature: Optional[float] = None) -> ChatGoogleGenerativeAI:
    """Return a process-wide LangChain Gemini client.

    Cached after the first call. We default to temperature 0 because every
    LLM call in this agent is structural (cleaning / segmentation / labeling)
    — creativity is the failure mode.
    """
    global _client
    if _client is not None and model is None and temperature is None:
        return _client

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set. "
            "Get one from https://aistudio.google.com/app/apikey."
        )

    client = ChatGoogleGenerativeAI(
        model=model or DEFAULT_MODEL,
        temperature=temperature if temperature is not None else DEFAULT_TEMPERATURE,
        google_api_key=api_key,
    )
    if model is None and temperature is None:
        _client = client
    return client


# ---------------------------------------------------------------------------
# JSON parsing — Gemini sometimes wraps output in markdown fences
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(s: str) -> str:
    m = _FENCE_RE.match(s.strip())
    return m.group(1) if m else s


def parse_json(raw: str) -> Any:
    """Parse a JSON payload that may be wrapped in markdown fences."""
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        logger.warning("LLM returned non-JSON output: %s", raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# High-level call
# ---------------------------------------------------------------------------


def call_json(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    fewshot: Optional[str] = None,
) -> Any:
    """Call the LLM with a system + (optional) fewshot + user message.

    The fewshot examples are appended to the system prompt — keeping them
    inside the system message benefits caching and signals "rules" rather
    than "data".
    """
    client = get_client(model=model, temperature=temperature)
    sys_text = system if not fewshot else f"{system}\n\n{fewshot}"
    response = client.invoke([
        SystemMessage(content=sys_text),
        HumanMessage(content=user),
    ])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    return parse_json(raw)
