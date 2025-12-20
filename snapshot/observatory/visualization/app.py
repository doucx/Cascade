import asyncio
import time
from asyncio import Queue
from typing import Any, Dict

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
        self.layout.split(
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)
        
        self.queue: Queue = Queue()
        self._running = False
        self._render_task: asyncio.Task | None = None

    def ingest_grid(self, x: int, y: int, state: float):
        """Asynchronously ingest a state update for a single cell in the grid."""
        self.queue.put_nowait(("grid", (x, y, state)))

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
        self.queue.put_nowait(("status", (key, value)))

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

    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        # Let the Live object manage the refresh rate entirely.
        with Live(self.layout, screen=True, transient=True, refresh_per_second=30) as live:
            last_time = time.perf_counter()
            frame_count = 0

            while self._running:
                # Process all pending updates from the queue.
                # This is a fast, non-blocking operation.
                while not self.queue.empty():
                    try:
                        msg_type, data = self.queue.get_nowait()
                        if msg_type == "grid":
                            x, y, state = data
                            self.grid_view.matrix.update(x, y, state)
                        elif msg_type == "status":
                            key, value = data
                            self.status_bar.set_status(key, value)
                    except asyncio.QueueEmpty:
                        break # Continue to physics step
                
                # Apply physics/decay to the grid
                self.grid_view.matrix.decay()

                # Update stats once per second for readability
                frame_count += 1
                now = time.perf_counter()
                if (now - last_time) > 1.0:
                    fps = frame_count / (now - last_time)
                    self.status_bar.set_status("FPS", f"{fps:.1f}")
                    self.status_bar.set_status("Queue", self.queue.qsize())
                    frame_count = 0
                    last_time = now
                
                # Crucially, we yield control to the event loop.
                # Rich's Live object will handle the sleep/wait to match refresh_per_second.
                await asyncio.sleep(0)