from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Path | None:
        try:
            # 这里的路径调整为相对于 cascade.bus 包
            locales_path = Path(__file__).parent / "locales"
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
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load message file {message_file}: {e}")

    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"
