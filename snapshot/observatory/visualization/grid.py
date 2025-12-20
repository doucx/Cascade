import numpy as np
import shutil
from typing import Callable

from rich.table import Table
from rich.box import MINIMAL
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment

# Re-using the matrix logic from protoplasm as it's solid
from observatory.protoplasm.renderer.matrix import StateMatrix, GridConfig

class GridView:
    """
    A Rich-renderable object that displays the state of a simulation grid.
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

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """The Rich render protocol method."""
        # Get a snapshot of the brightness matrix
        brightness = self.matrix.get_snapshot()
        # Get the corresponding colors using the palette
        colors = self.palette_func(brightness)
        
        # We use a simple table with no padding/borders for a clean grid
        table = Table.grid(padding=0)
        for _ in range(self.logical_width):
            table.add_column()

        # Build the grid row by row
        for y in range(self.logical_height):
            row_cells = []
            for x in range(self.logical_width):
                # Use a double-width block for square-like pixels
                char = "██"
                color_code = colors[y, x]
                style = color_code if color_code else "black"
                row_cells.append((char, style))
            
            # Rich Table expects strings with style markup
            table.add_row(*[f"[{style}]{char}" for char, style in row_cells])
            
        yield table