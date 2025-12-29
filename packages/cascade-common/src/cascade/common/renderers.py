import sys
import json
from typing import TextIO, Optional
from datetime import datetime, timezone

from cascade.common.messaging import MessageStore, protocols

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}


class CliRenderer(protocols.Renderer):
    def __init__(
        self,
        store: MessageStore,
        stream: Optional[TextIO] = None,
        min_level: str = "INFO",
    ):
        self._store = store
        self._stream = stream if stream is not None else sys.stderr
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            message = self._store.get(msg_id, **kwargs)
            print(message, file=self._stream)


class JsonRenderer(protocols.Renderer):
    def __init__(
        self,
        stream: Optional[TextIO] = None,
        min_level: str = "INFO",
    ):
        self._stream = stream if stream is not None else sys.stderr
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
                return repr(o)

            json_str = json.dumps(log_record, default=default_serializer)
            print(json_str, file=self._stream)
