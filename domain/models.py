from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Platform = Literal["tiktok", "douyin", "reels", "youtube"]
Variant = Literal["short", "long", "auto"]  # V0.2: youtube long-form vs short-form


@dataclass(frozen=True)
class Scene:
    id: int
    duration_sec: int
    visual: str
    voiceover: str
    subtitle: str
    bgm: str
    transition: str


@dataclass(frozen=True)
class Chapter:
    """V0.2: YouTube long-form chapter marker."""
    start_sec: int
    title: str


@dataclass(frozen=True)
class Script:
    title: str
    platform: Platform
    duration_sec: int
    hook: str
    scenes: list[Scene]
    cta: str
    tags: list[str]
    # V0.2 optional fields (YouTube long-form only; absent on short-form scripts)
    chapters: list[Chapter] = field(default_factory=list)
    seo_title: str = ""
    thumbnail_text: str = ""


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    content: str
    ts: str
    usage: dict | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass
class Session:
    id: str
    description: str
    platform: Platform
    duration_sec: int
    model: str
    created_at: str
    turns: list[Turn] = field(default_factory=list)
