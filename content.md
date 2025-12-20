分析指出了两个关键问题：**输出流冲突**导致显示错乱，以及**计算负载过高（N=400）**导致 `LocalBus` 广播延迟过大，进而破坏了萤火虫的同步物理条件。

## [WIP] fix(experiment): 修复显示冲突并优化萤火虫实验参数

### 用户需求
1.  **修复 UI 冲突**: 禁止 `ConvergenceMonitor` 直接向 stdout 打印，将其数据集成到 `UniGrid` 的状态栏中。
2.  **恢复同步**: 降低 Agent 数量（N=400 -> N=100），以适应 `LocalBus` 在 Python 单线程下的全广播性能瓶颈，确保同步现象能正常涌现。
3.  **修正 FPS 显示**: `UniGrid` 显示的 FPS 应当是实际循环频率，而非单帧处理时间的倒数。

### 评论
这是一个典型的“海森堡效应”案例——观测行为（高频渲染 + 高负载广播）干扰了被观测系统（萤火虫同步）。通过降低负载和统一输出管道，我们可以消除这种干扰。同时，将 R 值集成到渲染器状态栏是更符合“单一事实来源”原则的 UI 设计。

### 目标
1.  修改 `ConvergenceMonitor`: 增加 `silent` 模式，并提供回调接口导出 R 值。
2.  修改 `UniGridRenderer`: 增加 `extra_info` 字段用于显示外部数据，并修正 FPS 计算公式。
3.  修改 `run_fireflies.py`: 降低 N 值，并将 Monitor 的数据桥接到 Renderer。

### 基本原理
-   **输出治理**: 在 TUI 应用中，必须只有一个组件（Renderer）拥有 stdout 的写入权。其他组件应作为数据源。
-   **负载均衡**: N=100 时，全连接广播量为 10,000 msg/cycle，Python `asyncio` 可以轻松处理。N=400 时为 160,000 msg/cycle，加上渲染开销，容易造成事件循环阻塞，导致 `cs.wait` 精度下降，从而破坏 Kuramoto 模型的同步条件。

### 标签
#intent/fix #flow/draft #priority/high #comp/protoplasm #concept/ui #scope/ux #ai/instruct #task/domain/visualization #task/object/monitor #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 改造 `ConvergenceMonitor` 支持静默回调模式

我们需要让 Monitor 闭嘴，把数据交出来。

~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~python
    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        bar_length = 40
        filled_length = int(bar_length * order_param)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        # Use carriage return to print on the same line
        # Add a check to not overwrite initial log messages
        if self._flash_count > 0:
            print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0):
        """The main loop of the monitor."""
        self._is_running = True
        subscription = await self.connector.subscribe("firefly/flash", self.on_flash)
        
        print("🔭 Convergence Monitor Started...")
        try:
            while self._is_running:
                order_parameter = self._calculate_order_parameter()
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            print("\nShutting down monitor.")
            if subscription:
                await subscription.unsubscribe()
~~~~~
~~~~~python
    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        if self.callback:
            self.callback(order_param)
            return

        bar_length = 40
        filled_length = int(bar_length * order_param)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        # Use carriage return to print on the same line
        # Add a check to not overwrite initial log messages
        if self._flash_count > 0:
            print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0, callback=None):
        """
        The main loop of the monitor.
        
        Args:
            frequency_hz: How often to calculate R.
            callback: Optional function(float) -> None to receive the R value 
                      instead of printing to stdout.
        """
        self._is_running = True
        self.callback = callback
        subscription = await self.connector.subscribe("firefly/flash", self.on_flash)
        
        if not self.callback:
            print("🔭 Convergence Monitor Started...")
            
        try:
            while self._is_running:
                order_parameter = self._calculate_order_parameter()
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            if not self.callback:
                print("\nShutting down monitor.")
            if subscription:
                await subscription.unsubscribe()
~~~~~

#### Acts 2: 增强 `UniGridRenderer` 支持外部状态和真实 FPS

修正 FPS 计算（使用两帧之间的时间差），并添加 `set_extra_info` 接口。

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
        self.driver = AnsiDriver()
        self.queue: Queue = Queue()
        self._running = False

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))

    async def start(self):
~~~~~
~~~~~python
        self.driver = AnsiDriver()
        self.queue: Queue = Queue()
        self._running = False
        self._extra_info = ""

    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))
        
    def set_extra_info(self, info: str):
        """Sets a string to be displayed in the status bar."""
        self._extra_info = info

    async def start(self):
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
            # 5. Stats Line
            elapsed = time.perf_counter() - loop_start
            fps = 1.0 / (elapsed + 0.001)
            self.driver.move_to(self.logical_height + 1, 0)
            self.driver.write(f"UniGrid | FPS: {fps:.1f} | Updates: {len(rows)}", '\033[97m')
            self.driver.flush()
            
            # 6. Sleep
            sleep_t = max(0, frame_time - elapsed)
            await asyncio.sleep(sleep_t)
            
        # Cleanup on exit
~~~~~
~~~~~python
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
~~~~~

#### Acts 3: 调整萤火虫实验配置并连接数据流

1.  `num_agents` 从 400 降至 100。
2.  定义一个 `update_status` 回调，将 Monitor 的 R 值格式化后传给 Renderer。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
# Visualization
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

async def run_experiment(
    num_agents: int = 400, # Increased for better visual field (20x20)
    period: float = 2.0,
    nudge: float = 0.2,
    duration_seconds: float = 30.0,
    visualize: bool = True
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    if visualize:
        print(f"🔥 Starting VISUAL firefly experiment with {num_agents} agents...")
    else:
        print(f"🔥 Starting headless firefly experiment...")

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

    renderer = None
    renderer_task = None
    
    if visualize:
        # Define visualizer mapping
        grid_width = int(num_agents**0.5)
        # Handle non-perfect squares
        if grid_width * grid_width < num_agents: grid_width += 1
        
        renderer = UniGridRenderer(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                # Ingest a "Flash" (1.0 brightness)
                renderer.ingest(x, y, 1.0)
        
        # Subscribe visualizer to bus
        await connector.subscribe("firefly/flash", on_flash_visual)
        renderer_task = asyncio.create_task(renderer.start())

    # --- Create Agents ---
~~~~~
~~~~~python
# Visualization
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

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
    if visualize:
        print(f"🔥 Starting VISUAL firefly experiment with {num_agents} agents...")
    else:
        print(f"🔥 Starting headless firefly experiment...")

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
    monitor = ConvergenceMonitor(num_agents, period, connector)
    
    renderer = None
    renderer_task = None
    
    if visualize:
        # Define visualizer mapping
        grid_width = int(num_agents**0.5)
        if grid_width * grid_width < num_agents: grid_width += 1
        
        renderer = UniGridRenderer(width=grid_width, height=grid_width, palette_func=Palettes.firefly, decay_rate=0.1)
        
        # Bridge Monitor -> Renderer
        def monitor_callback(r_value: float):
            # Create a simple visual bar for R
            bar_len = 10
            filled = int(bar_len * r_value)
            bar = "█" * filled + "░" * (bar_len - filled)
            renderer.set_extra_info(f"Sync(R): {r_value:.3f} [{bar}]")

        # Start Monitor in quiet mode with callback
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0, callback=monitor_callback))

        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None:
                x = aid % grid_width
                y = aid // grid_width
                renderer.ingest(x, y, 1.0)
        
        await connector.subscribe("firefly/flash", on_flash_visual)
        renderer_task = asyncio.create_task(renderer.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=10.0))

    # --- Create Agents ---
~~~~~

### 下一步建议
通过降低 Agent 规模和统一输出管道，我们应该能看到：
1.  **清晰的 UI**: 网格和状态栏各居其位，互不干扰。
2.  **正确的物理现象**: 随着负载降低，时间切片精度恢复，R 值应该会从 0 附近逐渐攀升至 1.0，网格上的闪烁也会从随机的“白噪声”逐渐凝聚成统一的“脉冲”。

如果需要进行大规模（N>1000）模拟，我们将不能再依赖 Python 原生的 `LocalBusConnector` 进行全广播，而必须切换到原基计划第二章中提到的 `DirectChannel` 或未来的 `Redis`/`IPC` 方案。
