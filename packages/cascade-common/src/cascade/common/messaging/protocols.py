from typing import Protocol, Any


class Renderer(Protocol):
    def render(self, msg_id: str, level: str, **kwargs: Any) -> None: ...
