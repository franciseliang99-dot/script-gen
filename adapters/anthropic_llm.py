from __future__ import annotations

from typing import Iterator

import anthropic

from ports.llm import CachedSegment, LLMClient, LLMReply


class AnthropicLLM(LLMClient):
    """Adapter for Anthropic Messages API with prompt-cache placement.

    Cache policy:
      - system block always gets cache_control: ephemeral (1 breakpoint).
      - For each segment marked cache=True, the last content block of the last
        message in that segment gets cache_control: ephemeral.
      - Anthropic caps total breakpoints at 4. Caller is responsible for not
        marking more than 3 message segments.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._last_reply: LLMReply | None = None

    @property
    def last_reply(self) -> LLMReply | None:
        return self._last_reply

    def chat_stream(
        self,
        system: str,
        segments: list[CachedSegment],
        model: str,
        max_tokens: int,
    ) -> Iterator[str]:
        messages = self._render_messages(segments)
        system_blocks = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        with self._client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()

        text = "".join(b.text for b in final.content if b.type == "text")
        usage = final.usage.model_dump() if hasattr(final.usage, "model_dump") else dict(final.usage)
        self._last_reply = LLMReply(
            text=text,
            usage=usage,
            cache_read_input_tokens=getattr(final.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(final.usage, "cache_creation_input_tokens", 0) or 0,
        )

    @staticmethod
    def _render_messages(segments: list[CachedSegment]) -> list[dict]:
        rendered: list[dict] = []
        for seg in segments:
            if not seg.messages:
                continue
            for i, msg in enumerate(seg.messages):
                is_last_in_seg = i == len(seg.messages) - 1
                blocks = [{"type": "text", "text": msg["content"]}]
                if seg.cache and is_last_in_seg:
                    blocks[-1]["cache_control"] = {"type": "ephemeral"}
                rendered.append({"role": msg["role"], "content": blocks})
        return rendered
