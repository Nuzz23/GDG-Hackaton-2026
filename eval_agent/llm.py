"""LLM client wrapper with --pro support.

Two roles:
- "judge"   — used by `judge_open` (and `judge_flashcard` fuzzy fallback).
              In --pro mode this routes to Gemini 2.5 Pro with a separate key.
- "message" — used by `generate_student_message`. Always Gemini Flash.

Caches one client per (model, api_key) tuple. JSON parsing is shared with
the indexing agent: tolerant of markdown fences.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Auto-load .env so the agent works inside subprocesses (CLI, background
# tasks) without depending on the parent shell environment.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass

from eval_agent.models import LLMConfig

logger = logging.getLogger(__name__)


_FLASH_MODEL = "gemini-2.5-flash"
_PRO_MODEL = "gemini-2.5-pro"
_DEFAULT_TEMPERATURE = 0.0


# ---------------------------------------------------------------------------
# Config builder — fail loud at startup
# ---------------------------------------------------------------------------


def make_config(use_pro: bool = False) -> LLMConfig:
    """Build LLMConfig from env vars. Validates here, NOT at first call."""
    flash_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not flash_key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set. "
            "Get one at https://aistudio.google.com/app/apikey "
            "or put it in a .env file at the project root."
        )

    if use_pro:
        pro_key = os.environ.get("GEMINI_PRO_API_KEY")
        if not pro_key:
            raise RuntimeError(
                "--pro requested but GEMINI_PRO_API_KEY is not set. "
                "Either set that env var or drop --pro."
            )
        return LLMConfig(
            judge_model=_PRO_MODEL,
            message_model=_FLASH_MODEL,
            judge_api_key=pro_key,
            message_api_key=flash_key,
        )

    return LLMConfig(
        judge_model=_FLASH_MODEL,
        message_model=_FLASH_MODEL,
        judge_api_key=flash_key,
        message_api_key=flash_key,
    )


# ---------------------------------------------------------------------------
# Client cache — keyed by (model, key)
# ---------------------------------------------------------------------------


_clients: dict[tuple[str, str], ChatGoogleGenerativeAI] = {}


def _get_client(model: str, api_key: str) -> ChatGoogleGenerativeAI:
    key = (model, api_key)
    client = _clients.get(key)
    if client is None:
        client = ChatGoogleGenerativeAI(
            model=model,
            temperature=_DEFAULT_TEMPERATURE,
            google_api_key=api_key,
        )
        _clients[key] = client
    return client


def _client_for(config: LLMConfig, role: Literal["judge", "message"]):
    if role == "judge":
        return _get_client(config.judge_model, config.judge_api_key)
    return _get_client(config.message_model, config.message_api_key)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_fences(s: str) -> str:
    m = _FENCE_RE.match(s.strip())
    return m.group(1) if m else s


def parse_json(raw: str) -> Any:
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        logger.warning("LLM returned non-JSON output: %s", raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# High-level calls
# ---------------------------------------------------------------------------


def call_json(
    config: LLMConfig,
    role: Literal["judge", "message"],
    *,
    system: str,
    user: str,
    fewshot: Optional[str] = None,
) -> Any:
    """LLM call expecting a JSON response."""
    client = _client_for(config, role)
    sys_text = system if not fewshot else f"{system}\n\n{fewshot}"
    response = client.invoke([
        SystemMessage(content=sys_text),
        HumanMessage(content=user),
    ])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    return parse_json(raw)


def call_text(
    config: LLMConfig,
    role: Literal["judge", "message"],
    *,
    system: str,
    user: str,
) -> str:
    """LLM call expecting plain text (no JSON parsing)."""
    client = _client_for(config, role)
    response = client.invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return (
        response.content if isinstance(response.content, str) else str(response.content)
    ).strip()
