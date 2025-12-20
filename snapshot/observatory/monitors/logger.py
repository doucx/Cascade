import json
import time
from typing import IO


class JsonFileLogger:
    """
    A simple logger to write experiment telemetry to a file, one JSON object per line.
    """

    def __init__(self, filename: str):
        self.filename = filename
        self._file: IO | None = None

    def open(self):
        """Opens the log file for writing."""
        self._file = open(self.filename, "w", encoding="utf-8")

    def log(self, data: dict):
        """Logs a dictionary as a JSON line."""
        if not self._file:
            return

        # Add a timestamp for time-series analysis
        data_with_ts = {"ts": time.time(), **data}

        json.dump(data_with_ts, self._file)
        self._file.write("\n")
        self._file.flush()

    def close(self):
        """Closes the log file."""
        if self._file:
            self._file.close()
            self._file = None
