import numpy as np
import shutil
from typing import Callable

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment

# Re-using the matrix logic from protoplasm as it's solid
from .matrix import StateMatrix, GridConfig


class GridView:
    """
    A Rich-renderable object that displays the state of a simulation grid.
    This version is highly optimized to yield low-level Segments instead of
    building a heavy Table object, which dramatically improves performance.
    """

    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        palette_func: Callable[[np.ndarray], np.ndarray] = None,
        decay_per_second: float = 4.0,
    ):
        cols, rows = shutil.get_terminal_size()

        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)

        self.config = GridConfig(
            width=self.logical_width,
            height=self.logical_height,
            decay_per_second=decay_per_second,
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """
        Legacy Rich support. Used if wrapped in a Rich Layout.
        """
        # Fallback for static reporting if needed
        yield Segment("GridView(Raw Mode Active)")

    def render_frame_buffer(self) -> bytes:
        """
        Generates the full frame as a raw byte string.
        This is the "Raw Metal" mode.
        """
        brightness = self.matrix.get_snapshot()
        # colors is a numpy array of strings like "\033[38;2;...m"
        colors = self.palette_func(brightness)

        # ANSI Reset
        reset = "\033[0m"

        # 1. Add pixel char "██" to every color code in the array
        # This creates an array of strings like "\033[38;...m██"
        # We use numpy char module for vectorized concatenation if possible,
        # but standard list comp is surprisingly fast for string joining.
        # Let's try a hybrid approach: Pre-calculate the row strings.

        lines = []
        for y in range(self.logical_height):
            # Join the row into one huge string
            # OPTIMIZATION: We could cache the "██" part or use numpy char add,
            # but string join is extremely optimized in CPython.
            row_str = "".join(f"{code}██" for code in colors[y])
            lines.append(row_str + reset)

        # Join lines with newline
        full_frame = "\n".join(lines)

        return full_frame.encode("utf-8")
