import asyncio
import numpy as np
from typing import Callable
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container
from textual.reactive import reactive
from rich.text import Text

class GridView(Static):
    """A widget to display the simulation grid."""

    grid_data = reactive(np.zeros((1, 1), dtype=np.float32))
    palette_func: reactive[Callable | None] = reactive(None)

    def render(self) -> str:
        """Render the grid using Rich."""
        # Guard against rendering before palette_func is set
        if self.palette_func is None:
            return ""

        grid = self.grid_data
        colors = self.palette_func(grid)
        
        # Using double-width characters for square-like pixels
        full_block = "██"
        
        lines = []
        for y in range(grid.shape[0]):
            line_text = Text()
            for x in range(grid.shape[1]):
                color = colors[y, x]
                line_text.append(full_block, style=f"on {color}")
            lines.append(line_text)
            
        return "\n".join(str(line) for line in lines)

class VisualizerApp(App):
    """A Textual app for visualizing Cascade simulations."""

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]
    
    CSS = """
    Screen {
        overflow: hidden;
    }
    #main_container {
        align: center middle;
        height: 100%;
    }
    GridView {
        width: auto;
        height: auto;
    }
    """

    def __init__(
        self,
        width: int,
        height: int,
        palette_func: Callable,
        data_queue: asyncio.Queue,
        status_queue: asyncio.Queue,
    ):
        super().__init__()
        self.grid_width = width
        self.grid_height = height
        self.palette_func = palette_func
        self.data_queue = data_queue
        self.status_queue = status_queue
        self.grid_view = GridView()
        self.status_bar = Static("Initializing...", id="status_bar")

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main_container"):
            yield self.grid_view
        yield Footer()

    async def on_mount(self) -> None:
        """Called when app starts."""
        self.grid_view.grid_data = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
        self.grid_view.palette_func = self.palette_func
        # Start background tasks to listen for data
        self.set_interval(1 / 30.0, self.update_grid) # 30 FPS target
        self.set_interval(1 / 10.0, self.update_status) # Status updates less frequently

    async def update_grid(self) -> None:
        """Pulls the latest grid data from the queue."""
        try:
            # Drain the queue, only render the last frame
            latest_grid = None
            while not self.data_queue.empty():
                latest_grid = self.data_queue.get_nowait()
            
            if latest_grid is not None:
                self.grid_view.grid_data = latest_grid
        except asyncio.QueueEmpty:
            pass
            
    async def update_status(self) -> None:
        """Pulls the latest status text from the queue."""
        try:
            latest_status = None
            while not self.status_queue.empty():
                latest_status = self.status_queue.get_nowait()
            
            if latest_status is not None:
                self.query_one(Footer).show_title = False
                self.query_one(Footer).show_bindings = False
                self.query_one(Footer)._on_compose() # Force re-render of footer with new status
                self.query_one(Footer).add_key_text(latest_status)

        except asyncio.QueueEmpty:
            pass

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark
        
    def action_quit(self) -> None:
        self.exit()