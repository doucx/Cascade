import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: Dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Optional[Path]:
        try:
            locales_path = Path(__file__).parent.parent / "locales"
            if locales_path.is_dir():
                return locales_path
        except Exception:
            pass
        return None

    def _load_messages(self):
        locales_dir = self._find_locales_dir()
        if not locales_dir:
            logger.error("Message resource directory 'locales' not found.")
            return

        locale_path = locales_dir / self.locale
        if not locale_path.is_dir():
            return

        for message_file in locale_path.glob("*.json"):
            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    self._messages.update(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load message file {message_file}: {e}")

    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"


class Renderer(Protocol):
    def render(self, msg_id: str, level: str, **kwargs: Any) -> None: ...


class MessageBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        
        # The renderer is now responsible for everything
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)
    
    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

_default_store = MessageStore(locale="en")
bus = MessageBus(store=_default_store)