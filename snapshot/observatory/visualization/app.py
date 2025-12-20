import asyncio
import time
from asyncio import Queue
from typing import Any

import numpy as np
from rich.live import Live
from rich.layout import Layout

from .grid import GridView
from .status import StatusBar


class TerminalApp:
    """
    The main application class for managing the live terminal UI.
    It orchestrates the layout and handles data ingestion and rendering loop.
    """

    def __init__(self, grid_view: GridView, status_bar: StatusBar):
        self.grid_view = grid_view
        self.status_bar = status_bar

        self.layout = Layout()
        self.layout.split(Layout(name="main", ratio=1), Layout(name="footer", size=3))
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._frame_buffer = set()  # (x, y, state)
        self._running = False
        self._render_task: asyncio.Task | None = None

    def ingest_grid(self, x: int, y: int, state: float):
        """
        [Legacy] Asynchronously ingest a state update via Queue.
        WARNING: High overhead. Use direct_update_grid for high-frequency updates.
        """
        self.queue.put_nowait(("grid", (x, y, state)))

    def direct_update_grid(self, x: int, y: int, state: float):
        """
        Adds a grid update to the frame buffer for batch processing.
        This is extremely fast and non-blocking.
        """
        self._frame_buffer.add((x, y, state))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
        """
        Specialized ingestion for full-frame updates, bypassing the queue
        for efficiency as it's a single large data item.
        """
        self.grid_view.matrix.set_matrix(new_matrix)

    async def start(self):
        """Starts the live rendering loop."""
        self._running = True
        self._render_task = asyncio.create_task(self._render_loop())
        # Give it a moment to render the first frame
        await asyncio.sleep(0.05)

    def stop(self):
        """Stops the rendering loop."""
        self._running = False
        if self._render_task:
            self._render_task.cancel()

    async def _flush_buffer(self):
        """Applies all buffered updates to the grid matrix using vectorization."""
        if not self._frame_buffer:
            return

        # Atomically swap the buffer
        updates = self._frame_buffer
        self._frame_buffer = set()

        # --- Vectorization Magic ---
        # 1. Convert the set of tuples into an Nx3 NumPy array
        update_array = np.array(list(updates), dtype=np.float32)

        if update_array.size == 0:
            return

        # 2. Extract coordinate and state columns
        coords_x = update_array[:, 0].astype(int)
        coords_y = update_array[:, 1].astype(int)
        states = update_array[:, 2]
        
        # 3. Call the new vectorized update method
        self.grid_view.matrix.update_batch(coords_x, coords_y, states)


    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        # Reduce refresh rate to 15 FPS to save CPU for agents
        with Live(
            self.layout, screen=True, transient=True, refresh_per_second=15
        ) as live:
            frame_times = []
            last_time = time.perf_counter()

            while self._running:
                # --- Batch Updates ---
                await self._flush_buffer()

                # Process all pending updates from the queue (for status bar etc.)
                queue_size = self.queue.qsize()
                while not self.queue.empty():
                    try:
                        msg_type, data = self.queue.get_nowait()
                        if msg_type == "grid":  # Legacy path
                            x, y, state = data
                            self.grid_view.matrix.update(x, y, state)
                        elif msg_type == "status":
                            key, value = data
                            self.status_bar.set_status(key, value)
                    except asyncio.QueueEmpty:
                        break

                # Calculate dt (frame_time) for physics update
                now = time.perf_counter()
                frame_time = now - last_time
                last_time = now

                # Apply physics/decay to the grid using the calculated dt
                self.grid_view.matrix.decay(frame_time)

                frame_times.append(frame_time)
                if len(frame_times) > 10:
                    frame_times.pop(0)

                avg_frame_time = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg_frame_time if avg_frame_time > 0 else float("inf")
                self.status_bar.set_status("FPS", f"{fps:.1f}")
                self.status_bar.set_status("Queue", queue_size)

                # Live display is automatically refreshed by the context manager.
                # We add a small sleep to prevent a 100% CPU busy-loop.
                await asyncio.sleep(0.001)
