from typing import Any, Protocol


class Renderer(Protocol):
    def render(self, msg_id: str, level: str, **kwargs: Any) -> None: ...
