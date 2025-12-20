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
        decay_rate: float = 0.05
    ):
        cols, rows = shutil.get_terminal_size()
        
        self.logical_width = width if width > 0 else cols // 2
        self.logical_height = height if height > 0 else max(10, rows - 5)
        
        self.config = GridConfig(
            width=self.logical_width, 
            height=self.logical_height, 
            decay_rate=decay_rate
        )
        self.matrix = StateMatrix(self.config)
        self.palette_func = palette_func
        # Pre-cache styles to avoid parsing strings in the render loop
        self._style_cache: Dict[str, Style] = {}

    def _get_style(self, style_str: str) -> Style:
        """Caches Rich Style objects for performance."""
        if style_str not in self._style_cache:
            self._style_cache[style_str] = Style.parse(style_str)
        return self._style_cache[style_str]

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """The Rich render protocol method, optimized for performance."""
        brightness = self.matrix.get_snapshot()
        colors = self.palette_func(brightness)
        
        # Use a double-width block for square-like pixels
        char = "██"
        
        for y in range(self.logical_height):
            # Yield segments for one full row
            yield from [
                Segment(char, self._get_style(colors[y, x]))
                for x in range(self.logical_width)
            ]
            # Yield a newline to move to the next row
            yield Segment.line()