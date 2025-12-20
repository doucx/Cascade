import asyncio
import time
import shutil
import numpy as np
from asyncio import Queue
from dataclasses import dataclass
from typing import Callable, Optional

from .driver import AnsiDriver
from .buffer import RenderBuffer
from .matrix import StateMatrix, GridConfig

class UniGridRenderer:
    """
    Unified Grid Renderer.
    - Uses double-width characters ('██') for square pixels.
    - Decoupled State (Logic) from Appearance (Palette).
    - Asynchronous ingestion loop.
    """

    def __init__(
        self, 
        width: int = 0, 
        height: int = 0, 
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_rate: float = 0.05
    ):
        # Auto-detect size if not provided
        cols, rows = shutil.get_terminal_size()
        # Logical width is half of physical columns because we use 2 chars per pixel
        self.logical_width = width if width > 0 else cols // 2
        # Reserve lines for UI
        self.logical_height = height if height > 0 else max(10, rows - 3)
        
        self.config = GridConfig(
            width=self.logical_width, 
            height=self.logical_height, 
            decay_rate=decay_rate
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func
        
        # Physical buffers are 2x width
        self.phys_width = self.logical_width * 2
        self.buffer_prev = RenderBuffer(self.phys_width, self.logical_height)
        self.buffer_curr = RenderBuffer(self.phys_width, self.logical_height)
        
        self.driver = AnsiDriver()
        self.queue: Queue = Queue()
        self._running = False
        self._extra_info = ""

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))

    def ingest_full(self, matrix: np.ndarray):
        """Thread-safe ingestion of a full frame."""
        # Use a special tag for full frame updates
        self.queue.put_nowait(("FULL", matrix))
        
    def set_extra_info(self, info: str):
        """Sets a string to be displayed in the status bar."""
        self._extra_info = info

    async def start(self):
        self._running = True
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()
        await self._render_loop()

    def stop(self):
        self._running = False
        # Do not close immediately, let the loop exit naturally or force cleanup here?
        # Usually loop exit is cleaner, but for forced stop:
        self.driver.show_cursor()
        self.driver.move_to(self.logical_height + 2, 0)
        self.driver.flush()

    async def _render_loop(self):
        target_fps = 30
        frame_time = 1.0 / target_fps
        
        while self._running:
            loop_start = time.perf_counter()
            
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    item = self.queue.get_nowait()
                    if isinstance(item, tuple) and item[0] == "FULL":
                        # Full frame replacement
                        # We assume the shape matches or relies on numpy broadcasting if compatible
                        # Ideally, caller ensures shape match.
                        # We copy to avoid reference issues if caller mutates it later.
                        np.copyto(self.matrix.brightness, item[1])
                    else:
                        x, y, state = item
                        self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
            
            # 2. Physics (Decay)
            self.matrix.decay()
            
            # 3. Map to Physical Buffer
            # Get colors from palette (H, W)
            logical_colors = self.palette_func(self.matrix.brightness)
            
            # Expand to physical (H, W*2)
            # We use '█' for all visible pixels
            # If color is 'default dark', maybe print space? 
            # For Golly style, we usually print blocks everywhere.
            
            phys_colors = np.repeat(logical_colors, 2, axis=1)
            
            # Update Current Buffer
            self.buffer_curr.chars[:] = '█' # Solid block
            self.buffer_curr.colors = phys_colors
            
            # 4. Diff & Draw
            rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
            
            if len(rows) > 0:
                chars = self.buffer_curr.chars[rows, cols]
                colors = self.buffer_curr.colors[rows, cols]
                
                # Buffer writes
                for r, c, char, color in zip(rows, cols, chars, colors):
                    self.driver.move_to(r, c)
                    self.driver.write(char, color)
                
                # Update prev
                # Optim: Only copy diffs or swap references if we reconstruct full buffer?
                # RenderBuffer implementation expects in-place updates usually.
                self.buffer_prev.chars[rows, cols] = chars
                self.buffer_prev.colors[rows, cols] = colors
                
            # 5. Stats Line
            # Calculate REAL FPS based on total loop time
            now = time.perf_counter()
            real_fps = 1.0 / (now - loop_start + 0.00001)
            # Use a simpler moving average if needed, but this is instant FPS
            
            self.driver.move_to(self.logical_height + 1, 0)
            status_text = f"UniGrid | FPS: {real_fps:.1f} | Updates: {len(rows)} | {self._extra_info}"
            # Pad to clear line
            self.driver.write(f"{status_text:<80}", '\033[97m')
            self.driver.flush()
            
            # 6. Sleep to maintain Target FPS
            # We measure elapsed from start of loop logic
            logic_elapsed = time.perf_counter() - loop_start
            sleep_t = max(0, frame_time - logic_elapsed)
            await asyncio.sleep(sleep_t)
            
        # Cleanup on exit
        self.driver.show_cursor()
        self.driver.flush()