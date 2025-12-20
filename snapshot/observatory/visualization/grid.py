import numpy as np
import shutil
from typing import Callable

from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment
from rich.style import Style

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
        The Rich render protocol method, highly optimized for throughput.
        It bypasses Rich's style parsing by constructing raw ANSI strings.
        """
        brightness = self.matrix.get_snapshot()
        # colors now contains raw ANSI escape codes (e.g. "\033[38;2;...m")
        colors = self.palette_func(brightness)

        # ANSI Reset code to clear color at the end of each line
        reset = "\033[0m"

        # Vectorized string construction.
        # We iterate over rows and join the (color + block) strings.
        # This is significantly faster than creating 10,000 Segment objects.
        for y in range(self.logical_height):
            # Join all columns in this row: color_code + "██"
            # Since `colors` is a numpy array of strings, this loop is tight.
            row_content = "".join(f"{code}██" for code in colors[y])
            
            # Yield a single Segment for the entire row, plus the reset code.
            # Rich will output this raw text directly to the terminal.
            yield Segment(row_content + reset)
            yield Segment.line()
