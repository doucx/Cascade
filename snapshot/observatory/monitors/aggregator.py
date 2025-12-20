import asyncio
import time
import json
import numpy as np
from collections import defaultdict
from typing import IO


class MetricsAggregator:
    """
    Collects high-frequency metrics and logs their aggregate statistics
    (avg, max, min, count) at a fixed interval.
    """

    def __init__(self, filename: str, interval_s: float = 1.0):
        self.filename = filename
        self.interval = interval_s
        self._file: IO | None = None
        self._buffer = defaultdict(list)
        self._lock = asyncio.Lock()
        self._next_flush_time = time.time() + self.interval

    def open(self):
        """Opens the log file."""
        self._file = open(self.filename, "w", encoding="utf-8")

    def close(self):
        """Closes the log file."""
        if self._file:
            # Flush any remaining data before closing
            self._flush_and_log(force=True)
            self._file.close()
            self._file = None

    async def record(self, key: str, value: float):
        """Records a single metric data point."""
        async with self._lock:
            self._buffer[key].append(value)

    def _flush_and_log(self, force: bool = False):
        now = time.time()
        if not force and now < self._next_flush_time:
            return

        # --- Critical Section ---
        # Atomically swap buffer to minimize lock time
        # Note: In asyncio, lock isn't strictly needed for this part if there are no awaits,
        # but it's good practice for clarity and future-proofing.
        buffer_to_process = self._buffer
        self._buffer = defaultdict(list)
        # --- End Critical Section ---

        if not self._file or not buffer_to_process:
            self._next_flush_time = now + self.interval
            return

        stats = {"ts": now}
        for key, values in buffer_to_process.items():
            if not values:
                continue

            arr = np.array(values)
            stats[key] = {
                "avg": np.mean(arr),
                "max": np.max(arr),
                "min": np.min(arr),
                "sum": np.sum(arr),
                "count": len(values),
            }

        json.dump(stats, self._file, default=float)
        self._file.write("\n")
        self._file.flush()

        self._next_flush_time = now + self.interval

    async def run(self):
        """The main loop that periodically flushes the buffer."""
        while self._file is not None:
            self._flush_and_log()
            await asyncio.sleep(
                self.interval / 10
            )  # Wake up 10x per interval for responsiveness
