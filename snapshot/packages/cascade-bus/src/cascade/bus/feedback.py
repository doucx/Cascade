from __future__ import annotations

from typing import Any

from .messages import MessageStore
from .protocols import Renderer


class FeedbackBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Renderer | None = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
_default_store = MessageStore(locale="en")
bus = FeedbackBus(store=_default_store)
