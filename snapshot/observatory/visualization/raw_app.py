import asyncio
import sys
import time
from asyncio import Queue
from typing import Any, List, Tuple

import numpy as np

from .grid import GridView
from .status import StatusBar
from observatory.monitors.aggregator import MetricsAggregator

# ANSI Codes
CURSOR_HIDE = b"\033[?25l"
CURSOR_SHOW = b"\033[?25h"
CURSOR_HOME = b"\033[H"
CLEAR_SCREEN = b"\033[2J"
CLEAR_LINE = b"\033[K"
RESET_COLOR = b"\033[0m"


class RawTerminalApp:
    """
    A 'Raw Metal' renderer that bypasses Rich/Curses and writes directly
    to the stdout buffer.
    
    OPTIMIZED VERSION (v2):
    - Implements Lockless Double Buffering for high-frequency ingestion.
    - Uses Vectorized NumPy ingestion to eliminate Python iteration overhead.
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
        
        # --- Optimization: Double Buffering ---
        # We use a simple list for the back buffer.
        # Since 'direct_update_grid_batch' and '_render_loop' run in the same
        # asyncio event loop thread, simple list operations are atomic relative
        # to each other (no context switch during extend/assignment).
        self._back_buffer: List[Tuple[int, int, float]] = []
        
        self._running = False
        self._render_task: asyncio.Task | None = None

        self._stdout = sys.stdout.buffer

    async def direct_update_grid_batch(self, updates: List[Tuple[int, int, float]]):
        """
        Async batch update.
        
        PERFORMANCE NOTE:
        This is the hottest path in the system (called 2500+ times per flush).
        We removed the asyncio.Lock here. We simply extend the list.
        This operation is 'atomic' in the sense that the render loop cannot
        interrupt this function in the middle (cooperative multitasking).
        """
        if updates:
            self._back_buffer.extend(updates)

    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_grid(self, x: int, y: int, state: float):
        """
        Legacy sync ingestion for event callbacks.
        """
        self.queue.put_nowait(("grid", (x, y, state)))

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
        bar = f"\n\033[2m{'-' * self.grid_view.logical_width * 2}\033[0m\n"
        return (bar + line + "\033[K").encode("utf-8")

    def _blocking_flush_logic(self, updates_list: List[Tuple[int, int, float]]):
        """
        CPU-bound state update running in a separate thread.
        
        OPTIMIZATION:
        Replaced np.fromiter (slow Python loop) with np.array (fast C loop).
        """
        if not updates_list:
            return

        # 1. Vectorized Creation
        # Converting a list of tuples to a structured array is extremely fast in NumPy
        # shape will be (N, 3) where columns are x, y, state
        data = np.array(updates_list, dtype=np.float32)

        # 2. Vectorized Unpacking
        # We cast coordinates to int for indexing. 
        # Using astype(int) is very fast.
        x_coords = data[:, 0].astype(int)
        y_coords = data[:, 1].astype(int)
        states = data[:, 2]

        # 3. Vectorized Update
        self.grid_view.matrix.update_batch(x_coords, y_coords, states)

    async def _swap_and_process_buffer(self):
        """
        Async wrapper for flushing. 
        Implements the buffer swap logic.
        """
        # --- CRITICAL SECTION START ---
        # We swap the reference. The old list is detached and handed off to the thread.
        # A new list is put in place for incoming updates.
        # This is safe because we are single-threaded here.
        if not self._back_buffer:
            return 0
            
        updates_to_process = self._back_buffer
        self._back_buffer = [] 
        # --- CRITICAL SECTION END ---

        # Offload the heavy NumPy lifting to a thread
        await asyncio.to_thread(self._blocking_flush_logic, updates_to_process)
        return len(updates_to_process)

    async def _render_loop(self):
        last_time = time.perf_counter()

        # Cap at 60 FPS
        target_fps = 60.0
        frame_interval = 1.0 / target_fps

        while self._running:
            loop_start = time.perf_counter()

            # 1. Process Updates (Flush)
            flush_start = time.perf_counter()
            # This now handles the swap and the threaded processing
            updates_count = await self._swap_and_process_buffer()
            flush_ms = (time.perf_counter() - flush_start) * 1000

            # 2. Process Queue (Status & Legacy Grid)
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        k, v = data
                        self.status_bar.set_status(k, v)
                    elif msg_type == "grid":
                        x, y, s = data
                        # Direct update via matrix method (thread-safe enough for simple writes)
                        self.grid_view.matrix.update(x, y, s)
                except asyncio.QueueEmpty:
                    break

            # 3. Physics Step
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            physics_dt = min(dt, 0.1)
            self.grid_view.matrix.decay(physics_dt)

            # 4. RENDER
            output_buffer = bytearray(CURSOR_HOME)
            output_buffer.extend(self.grid_view.render_frame_buffer())
            output_buffer.extend(self._render_status_bar())

            self._stdout.write(output_buffer)
            self._stdout.flush()

            # 5. Telemetry & Sleep
            render_duration = time.perf_counter() - loop_start
            fps = 1.0 / dt if dt > 0 else 0
            
            self.status_bar.set_status("FPS", f"{fps:.1f}")

            if self.aggregator:
                # Log metrics for analysis
                # We expect flush_duration_ms to be MUCH lower now
                await self.aggregator.record("fps", fps)
                await self.aggregator.record("flush_duration_ms", flush_ms)

            sleep_time = frame_interval - render_duration
            
            if self.aggregator:
                jitter_ms = max(0, -sleep_time) * 1000
                await self.aggregator.record("render_jitter_ms", jitter_ms)

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0)