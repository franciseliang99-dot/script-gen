from __future__ import annotations

import os
from pathlib import Path

from adapters.anthropic_llm import AnthropicLLM
from adapters.jsonl_session_store import JsonlSessionStore
from app.script_agent import ScriptAgent


DEFAULT_MODEL = "claude-opus-4-7"


def _default_sessions_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "sessions"


def build_store(sessions_dir: str | Path | None = None) -> JsonlSessionStore:
    """Read-only paths (list, show) need only the store — skip API client init."""
    return JsonlSessionStore(sessions_dir or _default_sessions_dir())


def build_agent(
    *,
    model: str = DEFAULT_MODEL,
    sessions_dir: str | Path | None = None,
    max_tokens: int = 4096,
) -> tuple[ScriptAgent, JsonlSessionStore]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    llm = AnthropicLLM(api_key=api_key)
    store = build_store(sessions_dir)
    agent = ScriptAgent(llm=llm, store=store, model=model, max_tokens=max_tokens)
    return agent, store
