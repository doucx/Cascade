好的，我们继续推进，将 Conway 生命游戏的“孪生验证器”也迁移到新的 `UniGrid` 架构上，实现所有观测工具视觉风格的统一。

## [WIP] refactor(proto): Migrate Conway validation to UniGrid renderer

### 用户需求
1.  **迁移 Conway 渲染**: 将 `run_conway_experiment.py` 及其核心 `StateValidator` 从旧的、专用的 `TruthRenderer` 迁移到可复用的 `UniGridRenderer`。
2.  **统一视觉风格**: 确保 Conway 生命游戏的渲染也采用“正方形像素”（双宽字符），并使用新的调色板系统来显示“理论/实际”的差异。
3.  **同步测试**: 更新或移除 `test_renderer.py`，因为它依赖于已被废弃的 `TruthRenderer`。

### 评论
这是对 `UniGrid` 可复用性的终极考验。与萤火虫或瓶颈模拟不同，Conway 验证器需要渲染一个复杂的“差异状态”（匹配、鬼影、缺失），而不是简单的亮度值。成功迁移将证明我们的 `Palette` + `UniGrid` 架构足够灵活，能够作为未来所有网格可视化的统一基座。删除旧的测试脚本也是一个健康的重构步骤，因为它现在已经被更强大的主实验脚本所取代。

### 目标
1.  **扩展调色板**: 在 `palette.py` 中添加一个新的 `conway_diff` 调色板，将差异状态（0-3）映射到红/白/蓝/灰等颜色。
2.  **增强 `UniGrid`**: 为 `UniGridRenderer` 添加一个 `update_full_matrix` 方法，允许直接用一个新的状态矩阵覆盖当前状态，这对于回合制模拟比逐点 `ingest` 更高效。
3.  **重构 `StateValidator`**: 修改 `StateValidator`，使其不再拥有自己的渲染器，而是接收一个外部 `UniGridRenderer` 实例，并将计算出的差异矩阵和统计信息传递给它。
4.  **更新实验脚本**: 重写 `run_conway_experiment.py`，由它来初始化 `UniGridRenderer` 并注入到 `StateValidator` 中。
5.  **清理**: 删除已过时的 `observatory/protoplasm/truth/test_renderer.py`。

### 基本原理
新的工作流将是：
1.  `run_conway_experiment.py` 创建 `UniGridRenderer(palette=Palettes.conway_diff)` 和 `StateValidator(renderer=...)`。
2.  `StateValidator` 在其内部循环中计算出下一代的“差异矩阵”（一个包含 0, 1, 2, 3 值的 numpy 数组）。
3.  `StateValidator` 调用 `renderer.update_full_matrix(diff_matrix)` 和 `renderer.set_extra_info(...)`。
4.  `UniGridRenderer` 在其独立的渲染循环中，使用 `conway_diff` 调色板将差异矩阵转换为颜色，并绘制到屏幕上。
这个流程完美地将“计算”（Validator）和“渲染”（UniGrid）解耦。

### 标签
#intent/refine #flow/draft #priority/medium #comp/protoplasm #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/unigrid #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 为 Conway Diff 扩展调色板

我们在 `palette.py` 中添加一个新的静态方法来处理四种不同的验证状态。

~~~~~act
patch_file
observatory/protoplasm/renderer/palette.py
~~~~~
~~~~~python
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors
~~~~~
~~~~~python
        # Running (Bright White/Green tint)
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors

    @staticmethod
    def conway_diff(states: np.ndarray) -> np.ndarray:
        """
        Maps diff states to colors for Conway's Game of Life validation.
        0: Match-Dead (Dark Gray)
        1: Match-Alive (Bright White)
        2: False Positive / Ghost (Red)
        3: False Negative / Missing (Cyan)
        """
        colors = np.full(states.shape, '\033[38;2;40;40;40m', dtype='<U24') # 0: Dark Gray

        colors[states == 1] = '\033[38;2;240;240;240m' # 1: White
        colors[states == 2] = '\033[38;2;255;50;50m'   # 2: Red
        colors[states == 3] = '\033[38;2;50;200;255m'  # 3: Cyan

        return colors
~~~~~

#### Acts 2: 为 `UniGrid` 添加全矩阵更新能力

为了效率，我们添加一个方法来直接替换整个状态矩阵，跳过队列和衰减。

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))
        
    def set_extra_info(self, info: str):
        """Sets a string to be displayed in the status bar."""
        self._extra_info = info

    async def start(self):
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion for continuous events."""
        self.queue.put_nowait((x, y, state))

    def update_full_matrix(self, new_matrix: np.ndarray):
        """
        Directly sets the entire state matrix.
        Useful for turn-based simulations like Conway's Game of Life.
        This bypasses the event queue and decay logic.
        """
        if new_matrix.shape == self.matrix.brightness.shape:
            # We use the brightness matrix as our direct state holder here.
            np.copyto(self.matrix.brightness, new_matrix)
        
    def set_extra_info(self, info: str):
        """Sets a string to be displayed in the status bar."""
        self._extra_info = info

    async def start(self):
~~~~~

#### Acts 3: 重构 `StateValidator` 以使用外部渲染器

这是核心逻辑变更。`StateValidator` 现在是一个纯粹的计算和验证引擎。

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import numpy as np
from typing import Dict, Any, Optional

from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.protoplasm.renderer.unigrid import UniGridRenderer

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, renderer: Optional[UniGridRenderer] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        self.renderer = renderer
        
        self.buffer: Dict[int, Dict[int, Any]] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01) # Small sleep to yield control
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        gen = payload.get('gen')
        agent_id = payload.get('id')
        if gen is None or agent_id is None: return

        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            return

        current_buffer = self.buffer[next_gen]
        if len(current_buffer) < self.total_agents:
            return # Wait for all reports
            
        self._verify_and_render_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _verify_and_render_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid from agent reports
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
        self.history_actual[gen] = actual_grid

        # 2. Calculate Theoretical Grid (Golden Reference)
        if gen == 0:
            self.golden.seed(actual_grid)
            theoretical_grid = actual_grid.copy()
        else:
            prev_actual = self.history_actual.get(gen - 1)
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                theoretical_grid = self.golden.step()
                
                # Update error counts based on diff
                diff = np.sum(actual_grid != theoretical_grid)
                self.absolute_errors += diff
            else:
                # Fallback if history is missing
                theoretical_grid = actual_grid.copy()

        # 3. Render
        if self.renderer:
            # Create the diff matrix for the palette
            # 0=Dead, 1=Alive, 2=Ghost, 3=Missing
            diff_matrix = np.zeros_like(actual_grid, dtype=np.float32)
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 1)] = 1.0 # Match-Alive
            diff_matrix[(actual_grid == 1) & (theoretical_grid == 0)] = 2.0 # Ghost
            diff_matrix[(actual_grid == 0) & (theoretical_grid == 1)] = 3.0 # Missing

            self.renderer.update_full_matrix(diff_matrix)

            status_icon = "✅ SYNC" if self.absolute_errors == 0 else "❌ DRIFT"
            info = f"GEN: {gen} | Status: {status_icon} | Total Errors: {self.absolute_errors}"
            self.renderer.set_extra_info(info)

    def stop(self):
        self._running = False
~~~~~

#### Acts 4: 更新 Conway 实验的主脚本

现在脚本变得更简洁，只负责组装和启动组件。

~~~~~act
write_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
import asyncio
import numpy as np
import shutil

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.protoplasm.agents.conway import conway_agent
from observatory.protoplasm.truth.validator import StateValidator
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

MAX_GENERATIONS = 500

def get_random_seed(width: int, height: int, density: float = 0.2) -> np.ndarray:
    rng = np.random.default_rng()
    return (rng.random((height, width)) < density).astype(np.int8)

def calculate_neighbors(x, y, width, height):
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0: continue
            nx, ny = (x + dx) % width, (y + dy) % height
            neighbors.append(ny * width + nx)
    return neighbors

async def run_experiment():
    # 1. Setup Renderer
    renderer = UniGridRenderer(palette_func=Palettes.conway_diff, decay_rate=0.0)
    
    GRID_WIDTH = renderer.logical_width
    GRID_HEIGHT = renderer.logical_height
    
    print(f"🚀 Starting Conway Experiment with grid {GRID_WIDTH}x{GRID_HEIGHT}...")

    # 2. Setup Shared Infrastructure
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 3. Setup Validator, injecting the renderer
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, renderer=renderer)

    # 4. Setup Engine
    engine = cs.Engine(solver=cs.NativeSolver(), executor=cs.LocalExecutor(), bus=cs.MessageBus())
    @resource(name="shared_connector")
    def shared_connector_provider(): yield connector
    engine.register(shared_connector_provider)
    
    # 5. Create Initial State & Agent Workflows
    initial_grid = get_random_seed(GRID_WIDTH, GRID_HEIGHT, density=0.3)
    agent_workflows = [
        conway_agent(
            agent_id=(y * GRID_WIDTH + x), x=x, y=y,
            initial_state=int(initial_grid[y, x]),
            neighbor_ids=calculate_neighbors(x, y, GRID_WIDTH, GRID_HEIGHT),
            topic_base="cell", validator_topic="validator/report",
            connector=cs.inject("shared_connector"), max_generations=MAX_GENERATIONS
        )
        for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
    ]

    # 6. Run all components concurrently
    renderer_task = asyncio.create_task(renderer.start())
    validator_task = asyncio.create_task(validator.run())
    agent_tasks = [asyncio.create_task(engine.run(wf)) for wf in agent_workflows]
    
    try:
        await asyncio.gather(*agent_tasks)
    finally:
        validator.stop()
        renderer.stop() # This is now important to call
        for t in agent_tasks: t.cancel()
        
        # Ensure all tasks are awaited to prevent warnings
        await asyncio.gather(renderer_task, validator_task, *agent_tasks, return_exceptions=True)
        await connector.disconnect()
        print(f"\nExperiment Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(run_experiment())
    except KeyboardInterrupt:
        pass
~~~~~

#### Acts 5: 删除过时的测试渲染器脚本

`test_renderer.py` 的功能现在已经被 `run_conway_experiment.py` 完美覆盖，且后者是更真实的端到端测试。

~~~~~act
delete_file
observatory/protoplasm/truth/test_renderer.py
~~~~~
