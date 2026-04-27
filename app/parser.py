"""Tolerant JSON extraction from model responses.

Models occasionally wrap JSON in prose or ```json fences despite instructions.
We greedily find the first balanced top-level object and json.loads() it.
"""

from __future__ import annotations

import json

from domain.models import Scene, Script


def extract_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError("no '{' found in model output")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    raise ValueError("unbalanced braces in model output")


def parse_script(text: str) -> Script:
    raw = extract_json_object(text)
    data = json.loads(raw)
    return Script(
        title=data["title"],
        platform=data["platform"],
        duration_sec=int(data["duration_sec"]),
        hook=data["hook"],
        scenes=[
            Scene(
                id=int(s["id"]),
                duration_sec=int(s["duration_sec"]),
                visual=s["visual"],
                voiceover=s.get("voiceover", ""),
                subtitle=s.get("subtitle", ""),
                bgm=s.get("bgm", ""),
                transition=s.get("transition", ""),
            )
            for s in data["scenes"]
        ],
        cta=data.get("cta", ""),
        tags=list(data.get("tags", [])),
    )
