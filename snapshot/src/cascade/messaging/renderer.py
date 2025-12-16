import sys
from typing import TextIO

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

class CliRenderer:
    def __init__(self, stream: TextIO = sys.stderr, min_level: str = "INFO"):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def print(self, message: str, level: str):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            print(message, file=self._stream)