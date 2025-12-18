import re
from typing import Any, Callable

TAG_RE = re.compile(r"<(/?)([a-zA-Z0-9]+)([^>]*)>")
SELF_CLOSING_RE = re.compile(r"/\s*>$")


class TelegramHTMLSplitter:
    def __init__(self, send_func: Callable[..., Any], limit: int = 4096):
        self._send_func = send_func
        self._limit = limit
        self._buffer = ""
        self._tag_stack: list[str] = []

    def _closing_len(self) -> int:
        return sum(len(f"</{t}>") for t in self._tag_stack)

    def _will_fit(self, addition: str) -> bool:
        return len(self._buffer) + len(addition) + self._closing_len() <= self._limit

    async def _send_buffer(self) -> None:
        self._buffer = self._buffer.strip()
        if not self._buffer:
            return

        out = self._buffer + self._closing_tags(self._tag_stack)
        await self._send_func(out, parse_mode="HTML")

        self._buffer = self._opening_tags(self._tag_stack)

    async def add(self, html: str) -> None:
        if not self._will_fit(html):
            await self._send_buffer()

            # still too big → truncate
            if not self._will_fit(html):
                allowed = self._limit - len(self._buffer) - self._closing_len()
                if allowed > 1:
                    html = html[: allowed - 1] + "…"
                else:
                    return

        self._buffer += html
        self._update_tag_stack(self._tag_stack, html)

    async def flush(self) -> None:
        await self._send_buffer()
        self._buffer = ""
        self._tag_stack.clear()

    @staticmethod
    def _update_tag_stack(tag_stack: list[str], html: str) -> None:
        for match in TAG_RE.finditer(html):
            is_close, tag, _ = match.groups()

            if is_close:
                # pop until matching tag (defensive)
                while tag_stack and tag_stack[-1] != tag:
                    tag_stack.pop()
                if tag_stack:
                    tag_stack.pop()
            else:
                if not SELF_CLOSING_RE.search(match.group(0)):
                    tag_stack.append(tag)

    @staticmethod
    def _closing_tags(tag_stack: list[str]) -> str:
        return "".join(f"</{tag}>" for tag in reversed(tag_stack))

    @staticmethod
    def _opening_tags(tag_stack: list[str]) -> str:
        return "".join(f"<{tag}>" for tag in tag_stack)
