好的，我理解。Protoplasm 阶段的预研非常成功，我们验证了核心基础设施在极端负载下的可行性，并界定了性能边界。现在，我们进入了下一个阶段：将这些经过验证的原型（Protoplasm）固化为稳定、可复用、开发者友好的工具（Genesis SDK 的一部分）。

你对渲染器的分析完全正确。我们从头构建渲染器是为了理解性能瓶颈，这个目的已经达到。现在继续维护低级的 ANSI 驱动不仅效率低下，而且限制了我们未来的可视化能力。采用像 `rich` 这样成熟的库是明智之举，它能让我们专注于“渲染什么”，而不是“如何渲染”。

我将设计并实施一个新的、基于 `rich` 的模块化渲染器。它将取代 `protoplasm/renderer`，并成为未来所有观测实验的标准可视化后端。

## [WIP] refactor(observatory): 设计并实现一个模块化的、基于 Rich 的终端渲染器

### 用户需求
当前位于 `observatory/protoplasm/renderer` 的原型渲染器是为特定预研目的构建的，难以复用和扩展到新的实验（如 Conway's Game of Life）。我们需要一个健壮、模块化、易于维护的终端可视化解决方案，它应该：
1.  利用成熟的库（如 `rich`）来处理底层渲染。
2.  提供一个可组合的布局，至少包含一个网格视图和一个状态栏。
3.  保持 Protoplasm 阶段验证过的高性能、异步数据摄入模型。
4.  成为未来所有 CLI 可视化实验的标准工具。

### 评论
这是一个关键的重构，标志着项目从“可行性验证”阶段演进到“构建核心工具”阶段。用 `rich` 替换我们自己手写的 ANSI 驱动，可以极大地提升开发者体验（DX）和代码的可维护性，同时解锁更丰富的可视化潜力（如表格、面板、进度条等）。

将渲染器从 `protoplasm` 目录移出，建立一个新的 `observatory/visualization` 模块，也清晰地表明了它从一个临时原型“毕业”，成为了一个正式的、可长期依赖的组件。

### 目标
1.  创建一个新的 `observatory/visualization` 目录来存放标准化的可视化工具。
2.  设计并实现一个主应用类 `TerminalApp`，它使用 `rich.live.Live` 来管理整个渲染循环，并提供异步数据摄入接口。
3.  创建一个可复用的 `GridView` 组件，负责将 `numpy` 状态矩阵渲染成 `rich.table.Table`。
4.  创建一个 `StatusBar` 组件，负责显示实验的动态统计数据（如 FPS、Generation、同步参数 R 等）。
5.  将 `run_fireflies.py` 实验重构，用新的 `TerminalApp` 替换旧的 `UniGridRenderer`，以验证新系统的有效性。
6.  彻底删除已完成历史使命的 `observatory/protoplasm/renderer` 目录。

### 基本原理
新架构的核心是 `rich` 库的 `Live` 和 `Layout` 功能。
-   **`rich.live.Live`**: 作为一个上下文管理器，它能智能地处理终端屏幕的刷新，只重绘发生变化的部分，这与我们之前在 Protoplasm 中手动实现的“差异渲染”目标一致，但更强大和健壮。
-   **`rich.layout.Layout`**: 允许我们将屏幕分割成多个区域（如一个用于网格，一个用于状态栏），并将不同的 `rich` 可渲染对象（Renderables）放入其中。这天然地满足了模块化和可组合的需求。
-   **异步解耦**: 我们将保留 Protoplasm 验证过的 `asyncio.Queue` 数据摄入模型。实验逻辑通过 `app.ingest_grid()` 或 `app.update_status()` 将数据无阻塞地放入队列。`TerminalApp` 的异步渲染循环则独立地从队列中消费数据并更新 `rich` 组件的状态，从而确保模拟逻辑和渲染UI不会相互阻塞。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #concept/ui #scope/dx #ai/brainstorm #task/domain/visualization #task/object/terminal-renderer #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 建立新的可视化模块目录结构

首先，我们创建新的 `observatory/visualization` 目录，并为其添加初始化文件，使其成为一个 Python 模块。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p observatory/visualization
touch observatory/visualization/__init__.py
~~~~~

#### Acts 2: 实现核心渲染器组件

接下来，我们将创建构成新渲染器的三个核心文件。`app.py` 是主控制器，`grid.py` 负责网格渲染，`status.py` 负责状态栏。

~~~~~act
write_file
observatory/visualization/app.py
~~~~~
~~~~~python
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
~~~~~act
write_file
observatory/visualization/grid.py
~~~~~
~~~~~python
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
~~~~~
~~~~~act
write_file
observatory/visualization/status.py
~~~~~
~~~~~python
from rich.panel import Panel
from rich.text import Text
from rich.console import Console, ConsoleOptions, RenderResult
from typing import Dict, Any

class StatusBar:
    """
    A Rich-renderable object for displaying key-value status information.
    """
    def __init__(self, initial_status: Dict[str, Any] = None):
        self.status_data = initial_status or {}

    def set_status(self, key: str, value: Any):
        """Update a status value."""
        self.status_data[key] = value

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """The Rich render protocol method."""
        status_text = Text(no_wrap=True)
        for i, (key, value) in enumerate(self.status_data.items()):
            if i > 0:
                status_text.append(" | ", style="dim")
            status_text.append(f"{key}: ", style="cyan")
            status_text.append(str(value), style="bold magenta")
            
        yield Panel(status_text, title="[bold]Experiment Status[/bold]", border_style="dim")
~~~~~

#### Acts 3: 将萤火虫实验迁移到新渲染器

现在我们将 `run_fireflies.py` 实验更新为使用我们刚刚创建的新 `TerminalApp`。

~~~~~act
write_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
import time
from typing import Dict, Any

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor

# Visualization
from observatory.protoplasm.renderer.palette import Palettes
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar


async def run_experiment(
    num_agents: int = 100, # Reduced to 100 (10x10) to prevent LocalBus saturation
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    print(f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents...")

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    
    app = None
    app_task = None
    
    if visualize:
        grid_width = int(num_agents**0.5)
        if grid_width * grid_width < num_agents: grid_width += 1
        
        # 1. Create visualization components
        grid_view = GridView(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Sync (R)": "Initializing..."})
        app = TerminalApp(grid_view, status_bar)

        # 2. Bridge Monitor -> Status Bar
        def monitor_callback(r_value: float):
            bar_len = 20
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            app.update_status("Sync (R)", f"{r_value:.3f} [{bar}]")

        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0, callback=monitor_callback))

        # 3. Bridge Agent Flashes -> Grid
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                app.ingest_grid(x, y, 1.0)
        
        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

    # --- Create Agents ---
    agent_tasks = []
    
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    for i in range(num_agents):
        initial_phase = random.uniform(0, period)
        
        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None, 
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            flash_topic="firefly/flash",
            listen_topic="firefly/flash",
            connector=connector,
            refractory_period=period * 0.2,
        )
        
        agent_tasks.append(engine.run(agent_workflow))

    # --- Run ---
    all_agent_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.sleep(duration_seconds)
    except (Exception, asyncio.CancelledError) as e:
        print(f"Experiment interrupted or failed: {e}")
    finally:
        monitor.stop()
        if app: app.stop()
        
        if not all_agent_tasks.done():
            all_agent_tasks.cancel()
            await asyncio.gather(all_agent_tasks, return_exceptions=True)
            
        await asyncio.gather(monitor_task, return_exceptions=True)
        if app_task and not app_task.done():
            await app_task
        
        await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~

#### Acts 4: 移除废弃的原型渲染器

最后，我们删除旧的、不再需要的 `protoplasm/renderer` 目录，完成本次重构。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf observatory/protoplasm/renderer
~~~~~

### 下一步建议
1.  **迁移其他实验**: 逐步将 `run_conway_experiment.py` 和 `bottleneck_sim.py` 也迁移到使用新的 `TerminalApp` 渲染器，以统一所有实验的可视化后端。
2.  **增强 `StatusBar`**: 为 `StatusBar` 添加更丰富的功能，例如显示经过的时间、当前处理的事件速率、或特定于实验的自定义统计信息。
3.  **探索 `GridView` 调色板**: 为不同的实验（如 Conway's Game of Life）设计新的调色板函数，并将其添加到 `observatory/protoplasm/renderer/palette.py` 中，以更好地展示不同的状态。
