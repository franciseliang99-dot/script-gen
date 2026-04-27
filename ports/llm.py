from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass(frozen=True)
class LLMReply:
    text: str
    usage: dict
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


@dataclass(frozen=True)
class CachedSegment:
    """A run of messages that should share the cache breakpoint placed on its last block."""
    messages: list[dict]
    cache: bool


class LLMClient(Protocol):
    def chat_stream(
        self,
        system: str,
        segments: list[CachedSegment],
        model: str,
        max_tokens: int,
    ) -> Iterator[str]:
        """Yield text deltas. The full reply lands in `last_reply` after the iterator is exhausted."""
        ...

    @property
    def last_reply(self) -> LLMReply | None: ...
