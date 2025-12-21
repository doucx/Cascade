import asyncio
import sys
import time
from asyncio import Queue
from typing import Any, Optional

import numpy as np

from .grid import GridView
from .status import StatusBar
from observatory.monitors.aggregator import MetricsAggregator

# ANSI Codes
CURSOR_HIDE = b"\033[?25l"
CURSOR_SHOW = b"\033[?25h"
CURSOR_HOME = b"\033[H"
CLEAR_SCREEN = b"\033[2J"
RESET_COLOR = b"\033[0m"


class RawTerminalApp:
    """
    A 'Raw Metal' renderer that directly samples a shared state vector.
    """

    def __init__(
        self,
        grid_view: GridView,
        status_bar: StatusBar,
        state_vector: Optional[np.ndarray] = None, # The shared state
        aggregator: MetricsAggregator = None,
    ):
        self.grid_view = grid_view
        self.status_bar = status_bar
        self.state_vector = state_vector
        self.aggregator = aggregator

        self.queue: Queue = Queue() # Only for status updates now
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._stdout = sys.stdout.buffer

    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    async def start(self):
        self._running = True
        self._stdout.write(CURSOR_HIDE + CLEAR_SCREEN)
        self._stdout.flush()
        self._render_task = asyncio.create_task(self._render_loop())

    def stop(self):
        self._running = False
        if self._render_task:
            self._render_task.cancel()
        self._stdout.write(CURSOR_SHOW + RESET_COLOR + b"\n")
        self._stdout.flush()

    def _render_status_bar(self) -> bytes:
        parts = []
        for key, value in self.status_bar.status_data.items():
            parts.append(f"\033[36m{key}:\033[0m \033[1;35m{str(value)}\033[0m")
        line = " | ".join(parts)
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line + "\033[K").encode("utf-8")

    async def _render_loop(self):
        last_time = time.perf_counter()
        target_fps = 60.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()

            # 1. Process status queue
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        self.status_bar.set_status(data[0], data[1])
                except asyncio.QueueEmpty:
                    break

            # 2. Physics & State Update
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            
            # PULL from shared state vector
            if self.state_vector is not None:
                # Reshape the 1D vector into a 2D grid for the matrix
                grid_shape = (self.grid_view.logical_height, self.grid_view.logical_width)
                self.grid_view.matrix.set_matrix(self.state_vector.reshape(grid_shape))

            self.grid_view.matrix.decay(min(dt, 0.1))

            # 3. RENDER
            output_buffer = bytearray(CURSOR_HOME)
            grid_bytes = self.grid_view.render_frame_buffer()
            output_buffer.extend(grid_bytes)
            status_bytes = self._render_status_bar()
            output_buffer.extend(status_bytes)
            self._stdout.write(output_buffer)
            self._stdout.flush()

            # 4. Telemetry & Sleep
            fps = 1.0 / dt if dt > 0 else 0
            self.status_bar.set_status("FPS", f"{fps:.1f}")
            if self.aggregator:
                await self.aggregator.record("fps", fps)
            
            render_duration = time.perf_counter() - loop_start
            sleep_time = frame_interval - render_duration
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0) # Yield