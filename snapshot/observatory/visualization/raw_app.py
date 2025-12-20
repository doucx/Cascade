import asyncio
import sys
import time
from asyncio import Queue
from typing import Any

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
    A 'Raw Metal' renderer that bypasses Rich/Curses and writes directly 
    to the stdout buffer.
    """

    def __init__(
        self,
        grid_view: GridView,
        status_bar: StatusBar,
        aggregator: MetricsAggregator = None,
    ):
        self.grid_view = grid_view
        self.status_bar = status_bar
        self.aggregator = aggregator

        self.queue: Queue = Queue()
        self._frame_buffer = set()
        self._running = False
        self._render_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()

        # Pre-allocate numpy buffers for batch updates
        max_pixels = self.grid_view.logical_width * self.grid_view.logical_height
        self._update_coords_x = np.zeros(max_pixels, dtype=int)
        self._update_coords_y = np.zeros(max_pixels, dtype=int)
        self._update_states = np.zeros(max_pixels, dtype=np.float32)

        self._stdout = sys.stdout.buffer

    async def direct_update_grid_batch(self, updates: list):
        """Async batch update (same interface as TerminalApp)."""
        if not updates:
            return
        async with self._flush_lock:
            self._frame_buffer.update(updates)

    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
        """Direct full matrix update."""
        self.grid_view.matrix.set_matrix(new_matrix)

    async def start(self):
        """Starts the raw render loop."""
        self._running = True
        
        # Setup terminal
        self._stdout.write(CURSOR_HIDE)
        self._stdout.write(CLEAR_SCREEN)
        self._stdout.flush()
        
        self._render_task = asyncio.create_task(self._render_loop())

    def stop(self):
        """Stops the loop and restores terminal."""
        self._running = False
        if self._render_task:
            self._render_task.cancel()
        
        # Restore terminal
        self._stdout.write(CURSOR_SHOW)
        self._stdout.write(RESET_COLOR)
        self._stdout.write(b"\n")
        self._stdout.flush()

    def _render_status_bar(self) -> bytes:
        """
        Manually renders the status bar to bytes.
        Format: | Key: Value | Key: Value |
        """
        parts = []
        for key, value in self.status_bar.status_data.items():
            # Cyan Key, Magenta Value (Bold)
            parts.append(f"\033[36m{key}:\033[0m \033[1;35m{str(value)}\033[0m")
        
        line = " | ".join(parts)
        # Add a top border or separation
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line).encode("utf-8")

    def _blocking_flush_logic(self, updates_set):
        """CPU-bound state update."""
        num_updates = len(updates_set)
        if num_updates == 0:
            return

        # Flatten logic same as before
        temp_array = np.fromiter(
            (item for tpl in updates_set for item in tpl),
            dtype=np.float32,
            count=num_updates * 3,
        ).reshape((num_updates, 3))

        self._update_coords_x[:num_updates] = temp_array[:, 0]
        self._update_coords_y[:num_updates] = temp_array[:, 1]
        self._update_states[:num_updates] = temp_array[:, 2]

        self.grid_view.matrix.update_batch(
            self._update_coords_x[:num_updates],
            self._update_coords_y[:num_updates],
            self._update_states[:num_updates],
        )

    async def _flush_buffer(self):
        """Async wrapper for flushing."""
        updates_to_flush = None
        async with self._flush_lock:
            if self._frame_buffer:
                updates_to_flush = self._frame_buffer
                self._frame_buffer = set()

        if updates_to_flush:
            await asyncio.to_thread(self._blocking_flush_logic, updates_to_flush)
            return len(updates_to_flush)
        return 0

    async def _render_loop(self):
        last_time = time.perf_counter()
        
        # Target FPS
        target_fps = 30.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()

            # 1. Process Updates
            flush_start = time.perf_counter()
            updates_count = await self._flush_buffer()
            flush_ms = (time.perf_counter() - flush_start) * 1000

            # 2. Process Queue (Status)
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        k, v = data
                        self.status_bar.set_status(k, v)
                except asyncio.QueueEmpty:
                    break

            # 3. Physics Step
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            self.grid_view.matrix.decay(dt)

            # 4. RENDER (The heavy lifting)
            # Move cursor home
            output_buffer = bytearray(CURSOR_HOME)
            
            # Get Grid Bytes
            grid_bytes = self.grid_view.render_frame_buffer()
            output_buffer.extend(grid_bytes)
            
            # Get Status Bytes
            status_bytes = self._render_status_bar()
            output_buffer.extend(status_bytes)
            
            # WRITE TO STDOUT (Atomic-ish)
            self._stdout.write(output_buffer)
            self._stdout.flush()

            # 5. Telemetry & Sleep
            render_duration = time.perf_counter() - loop_start
            fps = 1.0 / dt if dt > 0 else 0
            
            self.status_bar.set_status("FPS", f"{fps:.1f}")
            
            if self.aggregator:
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            # Smart Sleep to maintain target FPS
            sleep_time = frame_interval - render_duration
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0) # Yield at least once