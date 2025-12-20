简要回答
我们遇到了典型的“主循环阻塞”和“生产者-消费者速率不匹配”问题。在 2500 个 Agent 的高频并发下，基于 Queue 的渲染管道成为了瓶颈，而过快的物理周期设置导致了严重的调度延迟（Jitter），破坏了同步机制。

我们需要打通渲染的“快速通道”，并实施“时间膨胀”策略。

## [WIP] tune(observatory): 建立渲染快速通道并实施时间膨胀策略

### 用户需求
1.  **解决 FPS 低和 Queue 堆积**: 渲染管道跟不上 Agent 的闪烁速度。
2.  **解决 Sync 失败**: 严重的 CPU 争用导致逻辑时间与物理时间脱节。

### 评论
当前的 `TerminalApp` 使用 `asyncio.Queue` 来串行化所有网格更新，这在低负载下是优雅的，但在 2500+ Agent 的并发冲击下（每秒可能产生数百次闪烁），Queue 成为了锁竞争的热点和延迟的来源。
同时，`PERIOD=3.0s` 对于纯 Python 的 `asyncio` 调度器来说太快了。处理 2500 个协程的唤醒和消息传递需要时间，如果物理周期太短，累积的调度延迟（Jitter）将超过相位容差，导致系统永远无法同步。
**解决方案**:
1.  **Bypass Queue**: 允许 Agent 回调直接修改 `StateMatrix`（利用 Python GIL 的原子性），消除 Queue 开销。
2.  **Time Dilation**: 将物理周期延长，降低系统的“心率”，给 CPU 足够的喘息时间来维持逻辑一致性。

### 目标
1.  修改 `TerminalApp` 以支持无锁、无队列的直接矩阵更新。
2.  调整 `run_fireflies.py` 参数，降低系统负载。

### 基本原理
1.  **GIL 作为互斥锁**: 在 CPython 中，对 NumPy 数组的切片赋值或简单算术操作通常是线程安全的（原子性的）。在 `asyncio` 单线程模型下，这更是绝对安全的。直接操作内存比通过 Queue 传递消息快几个数量级。
2.  **控制论**: 当控制回路的延迟（调度延迟）接近受控过程的时间常数（周期）时，系统必然失稳。降低过程频率是恢复稳定性的标准做法。

### 标签
#intent/tune #flow/ready #priority/critical #comp/observatory #scope/perf #task/domain/observatory #task/object/renderer #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 建立渲染快速通道

修改 `observatory/visualization/app.py`，允许直接更新网格，绕过 Queue。同时降低默认刷新率。

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
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

    def ingest_full_matrix(self, new_matrix: np.ndarray):
~~~~~
~~~~~new
        self.layout["main"].update(self.grid_view)
        self.layout["footer"].update(self.status_bar)

        self.queue: Queue = Queue()
        self._running = False
        self._render_task: asyncio.Task | None = None

    def ingest_grid(self, x: int, y: int, state: float):
        """
        [Legacy] Asynchronously ingest a state update via Queue.
        WARNING: High overhead. Use direct_update_grid for high-frequency updates.
        """
        self.queue.put_nowait(("grid", (x, y, state)))

    def direct_update_grid(self, x: int, y: int, state: float):
        """
        Directly updates the state matrix, bypassing the queue.
        Safe to call from async callbacks in the same event loop.
        """
        self.grid_view.matrix.update(x, y, state)

    def update_status(self, key: str, value: Any):
        """Asynchronously update a key-value pair in the status bar."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
~~~~~

~~~~~act
patch_file
observatory/visualization/app.py
~~~~~
~~~~~old
    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        with Live(
            self.layout, screen=True, transient=True, refresh_per_second=30
        ) as live:
            frame_times = []
            last_time = time.perf_counter()
~~~~~
~~~~~new
    async def _render_loop(self):
        """The core loop that processes the queue and updates the Live display."""
        # Reduce refresh rate to 15 FPS to save CPU for agents
        with Live(
            self.layout, screen=True, transient=True, refresh_per_second=15
        ) as live:
            frame_times = []
            last_time = time.perf_counter()
~~~~~

#### Acts 2: 应用快速通道与时间膨胀

修改 `observatory/experiments/run_fireflies.py`。
1. 使用 `app.direct_update_grid`。
2. 将 `PERIOD` 增加到 6.0s。
3. 将 Monitor 频率降低到 2.0Hz。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
# --- Constants ---
GRID_SIDE = 50
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 3.0


def get_neighbors(index: int, width: int, height: int) -> List[int]:
~~~~~
~~~~~new
# --- Constants ---
GRID_SIDE = 50
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 6.0  # Slowed down to allow CPU to catch up with 2500 agents


def get_neighbors(index: int, width: int, height: int) -> List[int]:
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~old
        monitor_task = asyncio.create_task(
            monitor.run(frequency_hz=10.0, callback=monitor_callback)
        )

        # 3. Bridge Agent Flashes -> Grid
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
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
~~~~~
~~~~~new
        monitor_task = asyncio.create_task(
            # Reduce monitor frequency to reduce CPU load
            monitor.run(frequency_hz=2.0, callback=monitor_callback)
        )

        # 3. Bridge Agent Flashes -> Grid
        # Agents now also publish to "firefly/flash" for the visualizer/monitor
        async def on_flash_visual(topic: str, payload: Dict[str, Any]):
            aid = payload.get("agent_id")
            if aid is not None and app:
                x = aid % grid_width
                y = aid // grid_width
                # Use Fast Path (Direct Update) to avoid queue bottlenecks
                app.direct_update_grid(x, y, 1.0)

        await connector.subscribe("firefly/flash", on_flash_visual)
        app_task = asyncio.create_task(app.start())
    else:
        # Headless mode: Monitor prints to stdout
        monitor_task = asyncio.create_task(monitor.run(frequency_hz=2.0))
~~~~~

### 下一步建议
运行修改后的实验。如果 Sync 仍然很差，考虑进一步增大 `nudge` 参数（例如从 0.2 增加到 0.5），或者继续延长 `PERIOD`。在纯 Python 环境下模拟大规模即时交互系统，我们是在挑战解释器的极限，必须找到那个“舒适区”。
