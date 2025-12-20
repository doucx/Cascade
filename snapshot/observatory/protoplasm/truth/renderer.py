import asyncio
import time
import numpy as np
import shutil
from typing import Tuple

# Reuse low-level drivers from the existing prototype
from observatory.protoplasm.renderer.driver import AnsiDriver
from observatory.protoplasm.renderer.buffer import RenderBuffer
from observatory.protoplasm.renderer.matrix import GridConfig

class DiffMatrix:
    """
    Manages the visual state of the verification grid.
    Values represent:
    0: Dead (Correct)
    1: Alive (Correct)
    2: False Positive (Ghost - Actual=1, Theory=0)
    3: False Negative (Missing - Actual=0, Theory=1)
    """
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)

    def update(self, actual: np.ndarray, theoretical: np.ndarray):
        """
        Computes the diff map.
        """
        # Reset
        self.grid.fill(0)
        
        # 1. Matches
        match_alive = (actual == 1) & (theoretical == 1)
        self.grid[match_alive] = 1
        
        # 2. False Positives (Red)
        false_pos = (actual == 1) & (theoretical == 0)
        self.grid[false_pos] = 2
        
        # 3. False Negatives (Blue)
        false_neg = (actual == 0) & (theoretical == 1)
        self.grid[false_neg] = 3

class TruthRenderer:
    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.matrix = DiffMatrix(width, height)
        
        self.buffer_prev = RenderBuffer(width, height)
        self.buffer_curr = RenderBuffer(width, height)
        self.driver = AnsiDriver()
        
        self._gen_counter = 0
        self._error_stats = {"abs": 0, "rel": 0}

    def start(self):
        self.driver.clear_screen()
        self.driver.hide_cursor()
        self.driver.flush()

    def stop(self):
        self.driver._buffer.clear()
        self.driver.show_cursor()
        self.driver.move_to(self.height + 4, 0)
        self.driver.flush()
        self.driver.close()

    def update_frame(self, gen: int, actual: np.ndarray, theoretical: np.ndarray, stats: dict):
        self._gen_counter = gen
        self._error_stats = stats
        self.matrix.update(actual, theoretical)
        self._render()

    def render_waiting(self, gen: int, current_count: int, total: int):
        """Updates only the progress line (Line 2) to show loading status."""
        # Move to Line 2 (height + 2)
        self.driver.move_to(self.height + 2, 0)
        
        progress = current_count / total if total > 0 else 0
        bar_len = 20
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Clear line first
        self.driver.write(f"{' ':<80}")
        self.driver.move_to(self.height + 2, 0)
        
        status = (
            f"Next Gen {gen}: [{bar}] {current_count}/{total}"
        )
        # Use dim color for waiting status
        self.driver.write(status, '\033[90m') 
        self.driver.flush()

    def _render(self):
        # 1. Rasterize Matrix to Buffer
        self.buffer_curr.chars[:] = ' '
        self.buffer_curr.colors[:] = ''
        
        grid = self.matrix.grid
        
        # Match Alive: White '#'
        mask_match = grid == 1
        self.buffer_curr.chars[mask_match] = '#'
        self.buffer_curr.colors[mask_match] = '\033[97m' # Bright White
        
        # Match Dead: Dim '.'
        mask_dead = grid == 0
        self.buffer_curr.chars[mask_dead] = '.'
        self.buffer_curr.colors[mask_dead] = '\033[90m' # Dark Gray
        
        # False Positive: Red 'X'
        mask_fp = grid == 2
        self.buffer_curr.chars[mask_fp] = 'X'
        self.buffer_curr.colors[mask_fp] = '\033[91m' # Bright Red
        
        # False Negative: Cyan 'O'
        mask_fn = grid == 3
        self.buffer_curr.chars[mask_fn] = 'O'
        self.buffer_curr.colors[mask_fn] = '\033[96m' # Bright Cyan

        # 2. Diff & Draw
        rows, cols = RenderBuffer.compute_diff(self.buffer_prev, self.buffer_curr)
        
        if len(rows) > 0:
            chars = self.buffer_curr.chars[rows, cols]
            colors = self.buffer_curr.colors[rows, cols]
            
            for r, c, char, color in zip(rows, cols, chars, colors):
                self.driver.move_to(r, c)
                self.driver.write(char, color)
            
            np.copyto(self.buffer_prev.chars, self.buffer_curr.chars)
            np.copyto(self.buffer_prev.colors, self.buffer_curr.colors)

        # 3. Status Line (Line 1)
        self.driver.move_to(self.height + 1, 0)
        
        total_err = self._error_stats['abs'] + self._error_stats['rel']
        status_icon = "✅ SYNC" if total_err == 0 else "❌ DRIFT"
        
        status = (
            f"GEN: {self._gen_counter:<4} | "
            f"Status: {status_icon} | "
            f"Total Err: {total_err:<4} | "
            f"(Abs: {self._error_stats['abs']}, Rel: {self._error_stats['rel']})"
        )
        self.driver.write(f"{status:<80}")
        
        # Clear the waiting line (Line 2) because we just finished a frame
        self.driver.move_to(self.height + 2, 0)
        self.driver.write(f"{' ':<80}")
        
        self.driver.flush()