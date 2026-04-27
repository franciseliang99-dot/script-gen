from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Iterator

from app.parser import parse_script
from app.prompts import build_initial_user_message, build_system_prompt
from domain.models import Script, Session, Turn
from ports.llm import CachedSegment, LLMClient
from ports.session_store import SessionStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_session_id(description: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = "".join(c if c.isalnum() else "-" for c in description[:24]).strip("-").lower() or "session"
    return f"{ts}-{safe}"


class ScriptAgent:
    def __init__(
        self,
        llm: LLMClient,
        store: SessionStore,
        *,
        model: str,
        max_tokens: int = 4096,
    ) -> None:
        self._llm = llm
        self._store = store
        self._model = model
        self._max_tokens = max_tokens
        self._system_prompt = build_system_prompt()

    def new_session(self, description: str, platform: str, duration_sec: int) -> Session:
        session_id = _make_session_id(description)
        if self._store.exists(session_id):
            session_id = session_id + "-" + datetime.now(timezone.utc).strftime("%f")
        session = Session(
            id=session_id,
            description=description,
            platform=platform,  # type: ignore[arg-type]
            duration_sec=duration_sec,
            model=self._model,
            created_at=_now_iso(),
        )
        self._store.create(session)
        first_user = build_initial_user_message(description, platform, duration_sec)
        for _ in self._iterate(session, first_user):
            pass
        return self._store.load(session_id)

    def iterate_stream(self, session_id: str, user_message: str) -> Iterator[str]:
        session = self._store.load(session_id)
        yield from self._iterate(session, user_message)

    def _iterate(self, session: Session, user_message: str) -> Iterator[str]:
        user_turn = Turn(role="user", content=user_message, ts=_now_iso())
        self._store.append_turn(session.id, user_turn)
        session.turns.append(user_turn)

        segments = self._build_segments(session.turns)

        chunks: list[str] = []
        for delta in self._llm.chat_stream(
            system=self._system_prompt,
            segments=segments,
            model=session.model,
            max_tokens=self._max_tokens,
        ):
            chunks.append(delta)
            yield delta

        reply = self._llm.last_reply
        full_text = "".join(chunks)
        assistant_turn = Turn(
            role="assistant",
            content=full_text,
            ts=_now_iso(),
            usage=reply.usage if reply else None,
            cache_read_input_tokens=reply.cache_read_input_tokens if reply else None,
            cache_creation_input_tokens=reply.cache_creation_input_tokens if reply else None,
        )
        self._store.append_turn(session.id, assistant_turn)

    @staticmethod
    def _build_segments(turns: list[Turn]) -> list[CachedSegment]:
        """Two segments: stable history (cache breakpoint on tail) + live tail.

        With system also cached, this gives 2 breakpoints per request — well
        under the 4-breakpoint limit and enough to cover this conversation
        pattern (last assistant turn becomes the cache anchor for the next).
        """
        msgs = [{"role": t.role, "content": t.content} for t in turns]
        if len(msgs) <= 1:
            return [CachedSegment(messages=msgs, cache=False)]

        last_assistant_idx = -1
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i]["role"] == "assistant":
                last_assistant_idx = i
                break

        if last_assistant_idx == -1:
            return [CachedSegment(messages=msgs, cache=False)]

        history = msgs[: last_assistant_idx + 1]
        tail = msgs[last_assistant_idx + 1 :]
        return [
            CachedSegment(messages=history, cache=True),
            CachedSegment(messages=tail, cache=False),
        ]


def latest_script(session: Session) -> Script | None:
    """Parse the most recent assistant turn into a Script, or None if absent / malformed."""
    for t in reversed(session.turns):
        if t.role == "assistant":
            try:
                return parse_script(t.content)
            except Exception:
                return None
    return None


def print_stream(stream: Iterator[str]) -> None:
    for delta in stream:
        sys.stdout.write(delta)
        sys.stdout.flush()
    sys.stdout.write("\n")
