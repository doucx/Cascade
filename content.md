Excellent feedback. This is exactly the kind of iterative refinement this "Protoplasm" phase is for. My initial migration to `rich` was functionally correct but naive in its implementation, leading to the precise issues you've identified: poor performance and degraded visual quality.

You are right to point them out. A tool that is "correct" but "unusable" is a failure. Let's fix this properly.

## [WIP] perf(visualization): Optimize GridView rendering and improve visual effects

### 错误分析
Your observations point to two distinct but related problems:

1.  **Performance (`卡顿`)**: The lag comes from my inefficient use of `rich`. In the current `GridView`, I am creating a new `rich.table.Table` object from scratch on *every single frame*. For a 100x50 grid, this means constructing an object with 5000 styled cells, which `rich.Live` then has to diff against the previous 5000-cell object. This object creation and deep comparison overhead is the source of the stuttering. The original renderer was faster because it did a simple `numpy` diff and only issued a few dozen ANSI commands for the changed pixels.

2.  **Visuals (`余晖效果变得很奇怪`)**: The unnatural afterglow is because my `firefly` palette now uses discrete, hard-coded color steps (`if brightness > 0.1`, `if > 0.6`, etc.). This creates harsh "bands" of color instead of a smooth, continuous gradient. The original `protoplasm` renderer, while primitive, had a more fluid decay model that I failed to replicate correctly in the `rich`-native palette.

### 用户需求
The visualization must be both performant and aesthetically pleasing. Specifically:
1.  The rendering loop must be smooth and not cause stuttering. An FPS counter is needed to quantify this.
2.  The "firefly" afterglow effect should be a smooth, continuous gradient from bright yellow to dark blue, not a series of jarring color jumps.

### 评论
This is a critical performance and quality-of-life tuning step. It moves our visualization tool from a "working prototype" to a "genuinely useful instrument". By addressing these issues, we ensure that the visualization does not interfere with the simulation itself and provides clear, intuitive insights. This refinement is essential before we can trust it for more complex experiments like Conway's Game of Life.

### 目标
1.  **Add FPS Monitoring**: Instrument the `TerminalApp`'s render loop to calculate and display the current Frames Per Second (FPS) in the `StatusBar`.
2.  **Optimize `GridView`**: Refactor `GridView.__rich_console__` to be dramatically more efficient. Instead of building a heavy `Table` object, it will be rewritten to yield low-level `Segment` objects directly, minimizing overhead and allowing `rich.Live` to perform much faster diffs.
3.  **Improve `Palettes`**: Rework the `firefly` palette function to use mathematical linear interpolation between color stops. This will replace the hard-coded thresholds with a smooth, continuous color gradient, restoring the natural afterglow effect.

### 基本原理
-   **Performance**: The key to performance with `rich.Live` is to make the renderable object as simple as possible. By ditching the `Table` class and yielding `Segment` objects (the most basic drawable unit in `rich`), we reduce the object graph that `rich` needs to traverse and diff each frame. We are essentially moving closer to the metal of `rich`'s rendering engine for our performance-critical component.
-   **Visuals**: We will define color "stops" (e.g., at brightness 0.0, 0.5, and 1.0) and use `numpy`'s vectorized operations to linearly interpolate the R, G, B values for every cell's brightness level simultaneously. This is computationally efficient and will produce a perfectly smooth gradient.
-   **Monitoring**: A simple moving average of frame times within the `TerminalApp`'s render loop will provide a stable FPS counter for the `StatusBar`.

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/cli #concept/ui #task/domain/visualization #task/object/rendering-performance #task/action/performance-tuning #task/state/continue

---
### Script

#### Acts 1: Instrument `TerminalApp` to Display FPS

First, we'll add an FPS counter to the main application loop so we can measure the impact of our optimizations.

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~python
    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        with Live(self.layout, screen=True, transient=True) as live:
            while self._running:
                # Process all pending updates from the queue
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
                        break
                
                # Apply physics/decay to the grid
                self.grid_view.matrix.decay()
                
                # Rich's Live object will handle the refresh automatically.
                # We can control the refresh rate here.
                await asyncio.sleep(1/30) # ~30 FPS
~~~~~
~~~~~python
    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        with Live(self.layout, screen=True, transient=True, refresh_per_second=30) as live:
            frame_times = []
            last_time = time.perf_counter()

            while self._running:
                # Process all pending updates from the queue
                queue_size = self.queue.qsize()
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
                        break
                
                # Apply physics/decay to the grid
                self.grid_view.matrix.decay()

                # Calculate FPS using a moving average of last 10 frames
                now = time.perf_counter()
                frame_time = now - last_time
                last_time = now
                frame_times.append(frame_time)
                if len(frame_times) > 10:
                    frame_times.pop(0)
                
                avg_frame_time = sum(frame_times) / len(frame_times)
                fps = 1.0 / avg_frame_time if avg_frame_time > 0 else float('inf')
                self.status_bar.set_status("FPS", f"{fps:.1f}")
                self.status_bar.set_status("Queue", queue_size)
                
                # Live display is automatically refreshed by the context manager.
                # We add a small sleep to prevent a 100% CPU busy-loop.
                await asyncio.sleep(0.001)
~~~~~

#### Acts 2: Implement Smooth Gradient in `palette.py`

Next, we'll fix the afterglow effect by replacing the discrete color steps with smooth linear interpolation.

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient using Rich-compatible styles.
        0.0 (Refractory/Quiet) -> Dark Blue/Black
        0.5 (Charging) -> Deep Orange
        1.0 (Flash) -> Bright Yellow/White
        """
        # Initialize with a dark background color in Rich's rgb format
        colors = np.full(brightness.shape, "rgb(30,30,40)", dtype="<U18")

        # Low energy (Charging): Reddish
        mask_low = (brightness > 0.1) & (brightness <= 0.6)
        colors[mask_low] = "rgb(100,40,40)"

        # High energy (Pre-flash): Orange
        mask_high = (brightness > 0.6) & (brightness <= 0.9)
        colors[mask_high] = "rgb(200,120,0)"

        # Flash: Bright Yellow/White
        mask_flash = brightness > 0.9
        colors[mask_flash] = "rgb(255,255,200)"

        return colors
~~~~~
~~~~~python
    @staticmethod
    def firefly(brightness: np.ndarray) -> np.ndarray:
        """
        Maps 0.0-1.0 brightness to a Firefly gradient using vectorized interpolation.
        """
        # Define color stops [R, G, B]
        stop1 = np.array([30, 30, 40])      # Dark Blue (at brightness 0.0)
        stop2 = np.array([200, 120, 0])     # Orange (at brightness 0.5)
        stop3 = np.array([255, 255, 200])   # Bright Yellow (at brightness 1.0)

        # Prepare output arrays
        r = np.zeros_like(brightness, dtype=np.uint8)
        g = np.zeros_like(brightness, dtype=np.uint8)
        b = np.zeros_like(brightness, dtype=np.uint8)

        # --- Vectorized Interpolation ---
        # Mask for the lower half of the gradient (0.0 to 0.5)
        mask1 = brightness <= 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t1 = brightness[mask1] * 2
        r[mask1] = (stop1[0] + (stop2[0] - stop1[0]) * t1).astype(np.uint8)
        g[mask1] = (stop1[1] + (stop2[1] - stop1[1]) * t1).astype(np.uint8)
        b[mask1] = (stop1[2] + (stop2[2] - stop1[2]) * t1).astype(np.uint8)

        # Mask for the upper half of the gradient (0.5 to 1.0)
        mask2 = brightness > 0.5
        # Normalize brightness in this range to 0-1 for interpolation
        t2 = (brightness[mask2] - 0.5) * 2
        r[mask2] = (stop2[0] + (stop3[0] - stop2[0]) * t2).astype(np.uint8)
        g[mask2] = (stop2[1] + (stop3[1] - stop2[1]) * t2).astype(np.uint8)
        b[mask2] = (stop2[2] + (stop3[2] - stop2[2]) * t2).astype(np.uint8)

        # Create rich-compatible "rgb(r,g,b)" strings. This is the slowest part.
        # We can optimize if needed, but it's more readable for now.
        return np.array([f"rgb({r_},{g_},{b_})" for r_, g_, b_ in zip(r.flat, g.flat, b.flat)]).reshape(r.shape)
~~~~~

#### Acts 3: Optimize `GridView` by using low-level `Segment` rendering

Finally, the most important change: we'll refactor `GridView` to eliminate the slow, per-frame `Table` creation.

~~~~~act
patch_file
observatory/visualization/grid.py
~~~~~
~~~~~python
from rich.table import Table
from rich.box import MINIMAL
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment

# Re-using the matrix logic from protoplasm as it's solid
from .matrix import StateMatrix, GridConfig

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
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
1.  **验证修复**: 请再次运行 `python -m observatory.experiments.run_fireflies`。您应该会看到一个 FPS 计数器，注意到卡顿现象已显著改善，并且萤火虫的余晖效果现在是平滑自然的渐变。
2.  **继续迁移**: 在确认性能和视觉效果达标后，我们可以充满信心地将 `run_conway_experiment.py` 和 `bottleneck_sim.py` 迁移到这个经过优化的可视化框架上。
