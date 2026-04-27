from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from domain.models import Session, Turn
from ports.session_store import SessionStore


class JsonlSessionStore(SessionStore):
    """Per-session JSONL file plus an index.jsonl for listing.

    Layout:
        <root>/<session-id>.jsonl   — header line + one JSON line per turn
        <root>/index.jsonl          — one JSON line per session (id, created_at, description, model)

    Append-only writes use O_APPEND for crash safety; rebuilding state means
    re-reading the file end-to-end.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._index = self._root / "index.jsonl"

    def _path(self, session_id: str) -> Path:
        if "/" in session_id or ".." in session_id:
            raise ValueError(f"unsafe session id: {session_id!r}")
        return self._root / f"{session_id}.jsonl"

    def exists(self, session_id: str) -> bool:
        return self._path(session_id).exists()

    def create(self, session: Session) -> None:
        path = self._path(session.id)
        if path.exists():
            raise FileExistsError(f"session already exists: {session.id}")
        header = {
            "kind": "header",
            "id": session.id,
            "description": session.description,
            "platform": session.platform,
            "duration_sec": session.duration_sec,
            "model": session.model,
            "created_at": session.created_at,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(header, ensure_ascii=False) + "\n")
        with self._index.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "id": session.id,
                        "description": session.description,
                        "platform": session.platform,
                        "duration_sec": session.duration_sec,
                        "model": session.model,
                        "created_at": session.created_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def append_turn(self, session_id: str, turn: Turn) -> None:
        path = self._path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"no such session: {session_id}")
        record = {"kind": "turn", **asdict(turn)}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self, session_id: str) -> Session:
        path = self._path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"no such session: {session_id}")
        header: dict | None = None
        turns: list[Turn] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                kind = rec.pop("kind")
                if kind == "header":
                    header = rec
                elif kind == "turn":
                    turns.append(Turn(**rec))
        if header is None:
            raise ValueError(f"session file missing header: {session_id}")
        return Session(
            id=header["id"],
            description=header["description"],
            platform=header["platform"],
            duration_sec=header["duration_sec"],
            model=header["model"],
            created_at=header["created_at"],
            turns=turns,
        )

    def list(self, limit: int = 20) -> list[dict]:
        if not self._index.exists():
            return []
        rows: list[dict] = []
        with self._index.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[:limit]
