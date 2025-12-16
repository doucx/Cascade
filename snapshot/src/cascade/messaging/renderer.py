import sys
import json
import time
from typing import TextIO
from datetime import datetime, timezone

from .bus import MessageStore, Renderer

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}


class CliRenderer:
    """
    Renders messages as human-readable, formatted text strings.
    """
    def __init__(
        self,
        store: MessageStore,
        stream: TextIO = sys.stderr,
        min_level: str = "INFO",
    ):
        self._store = store
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            # Handle specific transformations for human-readable output
            if "target_tasks" in kwargs:
                kwargs["targets"] = ", ".join(kwargs["target_tasks"])

            template = self._store.get(msg_id)
            try:
                message = template.format(**kwargs)
            except KeyError as e:
                message = f"<Formatting error for '{msg_id}': missing key {e}>"

            print(message, file=self._stream)


class JsonRenderer:
    """
    Renders messages as structured, JSON-formatted strings.
    """
    def __init__(
        self,
        stream: TextIO = sys.stderr,
        min_level: str = "INFO",
    ):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            log_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level.upper(),
                "event_id": msg_id,
                "data": kwargs,
            }

            def default_serializer(o):
                """Handle non-serializable objects gracefully."""
                return repr(o)

            json_str = json.dumps(log_record, default=default_serializer)
            print(json_str, file=self._stream)