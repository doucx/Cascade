简要回答
我们将通过扩展 `UniGrid` 支持全帧注入 (`ingest_full`)，并实现一个新的 `truth` 调色板，来统一生命游戏的渲染架构。这将允许我们移除旧的 `TruthRenderer`，同时保留所有监控能力。

# [PASS]

## [WIP] refactor(proto): 统一 Conway 实验至 UniGrid 渲染架构

### 用户需求
将 Conway 生命游戏实验及其验证器 (`StateValidator`) 从专用的 `TruthRenderer` 迁移到通用的 `UniGridRenderer`，同时保留进度条、Diff 可视化和测试基准。

### 评论
这次重构验证了 `UniGrid` 架构的通用性——它不仅能处理基于事件的稀疏更新（萤火虫），也能高效处理基于帧的密集更新（生命游戏）。通过引入 `ingest_full` 接口，我们将 `UniGrid` 升级为一个真正的高性能通用终端渲染器。

### 目标
1.  **扩展 UniGrid**: 实现 `ingest_full` 用于批量更新，优化密集型渲染性能。
2.  **实现 Truth Palette**: 在 `Palettes` 中增加用于显示 Diff 状态（正确、假阳、假阴）的配色方案。
3.  **重构 Validator**: 使用 `UniGrid` 替换 `TruthRenderer`，并将状态逻辑映射到新的调色板值。
4.  **清理代码**: 移除过时的 `truth/renderer.py`。

### 基本原理
我们利用浮点状态值来编码分类信息（0.0=死, 1.0=活, 2.0=假阳, 3.0=假阴），从而复用 `UniGrid` 的数值矩阵处理能力。`ingest_full` 通过绕过单点更新队列，直接替换底层矩阵，解决了全网格同步时的性能瓶颈。

### 标签
#intent/refine #flow/ready #priority/medium #comp/docs #intent/tooling #scope/core #task/domain/visualization #task/object/unigrid #task/action/unify #task/state/begin

---

### Script

#### Acts 1: 扩展调色板

首先，我们在 `Palettes` 中添加 `truth` 方法，定义 Diff 状态的颜色映射。

~~~~~act
patch_file
observatory/protoplasm/renderer/palette.py
~~~~~
~~~~~python
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors
~~~~~
~~~~~python
        mask_run = states >= 0.8
        colors[mask_run] = '\033[38;2;200;255;200m'
        
        return colors

    @staticmethod
    def truth(states: np.ndarray) -> np.ndarray:
        """
        Maps states to Truth/Diff colors.
        0.0: Match Dead (Dark Gray)
        1.0: Match Alive (Bright White)
        2.0: False Positive (Red)
        3.0: False Negative (Cyan)
        """
        colors = np.full(states.shape, '\033[90m', dtype='<U24') # Match Dead
        
        # Match Alive (1.0)
        mask_alive = (states > 0.9) & (states < 1.1)
        colors[mask_alive] = '\033[97m' # Bright White

        # False Positive (2.0) - Red
        mask_fp = (states > 1.9) & (states < 2.1)
        colors[mask_fp] = '\033[91m'

        # False Negative (3.0) - Cyan
        mask_fn = (states > 2.9) & (states < 3.1)
        colors[mask_fn] = '\033[96m'
        
        return colors
~~~~~

#### Acts 2: 升级 UniGridRenderer

我们需要让 `UniGridRenderer` 支持接收全帧数据。这将通过在队列中传递特殊的消息元组来实现。

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))
        
    def set_extra_info(self, info: str):
~~~~~
~~~~~python
    def ingest(self, x: int, y: int, state: float = 1.0):
        """Thread-safe ingestion."""
        self.queue.put_nowait((x, y, state))

    def ingest_full(self, matrix: np.ndarray):
        """Thread-safe ingestion of a full frame."""
        # Use a special tag for full frame updates
        self.queue.put_nowait(("FULL", matrix))
        
    def set_extra_info(self, info: str):
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/unigrid.py
~~~~~
~~~~~python
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    x, y, state = self.queue.get_nowait()
                    self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
~~~~~
~~~~~python
            # 1. Process Queue
            while not self.queue.empty():
                try:
                    item = self.queue.get_nowait()
                    if isinstance(item, tuple) and item[0] == "FULL":
                        # Full frame replacement
                        # We assume the shape matches or relies on numpy broadcasting if compatible
                        # Ideally, caller ensures shape match.
                        # We copy to avoid reference issues if caller mutates it later.
                        np.copyto(self.matrix.brightness, item[1])
                    else:
                        x, y, state = item
                        self.matrix.update(x, y, state)
                except asyncio.QueueEmpty:
                    break
~~~~~

#### Acts 3: 重构 StateValidator

现在我们将 `StateValidator` 改为使用 `UniGridRenderer`。我们将状态计算逻辑移入 `_verify_generation`，并将进度信息传递给 `set_extra_info`。

~~~~~act
write_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
import asyncio
import time
import numpy as np
from typing import Dict, Any, List, Optional
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
# Replace old renderer with UniGrid
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes

class StateValidator:
    def __init__(self, width: int, height: int, connector: Connector, enable_ui: bool = True):
        self.width = width
        self.height = height
        self.connector = connector
        self.golden = GoldenLife(width, height)
        
        # UI: Use UniGrid with Truth Palette and 0 decay
        self.enable_ui = enable_ui
        self.renderer = None
        if enable_ui:
            self.renderer = UniGridRenderer(
                width=width, 
                height=height, 
                palette_func=Palettes.truth,
                decay_rate=0.0 # No decay for discrete CA states
            )
        
        # buffer[gen][agent_id] = state
        self.buffer: Dict[int, Dict[int, int]] = {}
        
        # History
        self.history_theoretical: Dict[int, np.ndarray] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.absolute_errors = 0
        self.relative_errors = 0
        self.max_gen_verified = -1

    async def run(self):
        self._running = True
        if self.renderer:
            # UniGrid start is an async task
            self._renderer_task = asyncio.create_task(self.renderer.start())
        else:
            print(f"⚖️  Validator active. Grid: {self.width}x{self.height}. Dual-Truth Mode Enabled.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()
            if self.renderer:
                self.renderer.stop()
                if not self._renderer_task.done():
                    self._renderer_task.cancel()
                    await self._renderer_task

    async def on_report(self, topic: str, payload: Any):
        """
        Payload: {id, coords: [x, y], gen, state}
        """
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
            
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            self._update_ui_status(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            self._update_ui_status(next_gen, len(current_buffer))
            return
            
        self._verify_generation(next_gen, current_buffer)
        
        del self.buffer[next_gen]
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
        if next_gen - 2 in self.history_theoretical:
            del self.history_theoretical[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_ui_status(self, gen: int, current: int):
        if not self.renderer:
            return
            
        total = self.total_agents
        progress = current / total if total > 0 else 0
        bar_len = 10
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        status_icon = "✅" if (self.absolute_errors + self.relative_errors) == 0 else "❌"
        
        info = (
            f"Gen {gen}: [{bar}] | "
            f"{status_icon} Err: {self.absolute_errors+self.relative_errors} "
            f"(Abs:{self.absolute_errors} Rel:{self.relative_errors})"
        )
        self.renderer.set_extra_info(info)

    def _verify_generation(self, gen: int, reports: Dict[int, Any]):
        # 1. Construct Actual Grid
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in reports.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        self.history_actual[gen] = actual_grid

        # 2. Base Case: Gen 0
        if gen == 0:
            self.golden.seed(actual_grid)
            self.history_theoretical[0] = actual_grid
            theo_grid = actual_grid
        else:
            # 3. Validation Logic
            prev_theo = self.history_theoretical.get(gen - 1)
            theo_grid = actual_grid # Fallback
            
            if prev_theo is not None:
                self.golden.seed(prev_theo)
                theo_grid = self.golden.step()
                self.history_theoretical[gen] = theo_grid
                
                diff_abs = np.sum(actual_grid != theo_grid)
                if diff_abs > 0:
                    self.absolute_errors += diff_abs

            # Check B: Relative Truth
            prev_actual = self.history_actual.get(gen - 1)
            if prev_actual is not None:
                self.golden.seed(prev_actual)
                expected_relative = self.golden.step()
                diff_rel = np.sum(actual_grid != expected_relative)
                if diff_rel > 0:
                    self.relative_errors += diff_rel

        # 4. Visualization Update
        if self.renderer:
            # Encode states for Palette.truth
            # 0.0: Match Dead
            # 1.0: Match Alive
            # 2.0: False Positive
            # 3.0: False Negative
            
            display_grid = np.zeros(actual_grid.shape, dtype=np.float32)
            
            # Match Alive
            display_grid[(actual_grid == 1) & (theo_grid == 1)] = 1.0
            # False Positive
            display_grid[(actual_grid == 1) & (theo_grid == 0)] = 2.0
            # False Negative
            display_grid[(actual_grid == 0) & (theo_grid == 1)] = 3.0
            
            # Ingest Full Frame
            self.renderer.ingest_full(display_grid)
            
            # Force status update
            self._update_ui_status(gen + 1, 0)

    def stop(self):
        self._running = False
~~~~~

#### Acts 4: 更新测试脚本

更新 `test_renderer.py` 以使用 `UniGridRenderer`。这是一个重要的验证步骤，确保新架构能正确显示我们期望的图案。

~~~~~act
write_file
observatory/protoplasm/truth/test_renderer.py
~~~~~
~~~~~python
import asyncio
import numpy as np
import shutil
import random

# Use the new UniGrid
from observatory.protoplasm.renderer.unigrid import UniGridRenderer
from observatory.protoplasm.renderer.palette import Palettes
from observatory.protoplasm.truth.golden_ca import GoldenLife

# --- Test Configuration ---
GRID_WIDTH = 40
GRID_HEIGHT = 20
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05  # seconds

def get_glider_seed(width: int, height: int) -> np.ndarray:
    """Creates a simple Glider pattern on the grid."""
    grid = np.zeros((height, width), dtype=np.int8)
    #   .X.
    #   ..X
    #   XXX
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid

async def main():
    """
    Main loop to test the UniGridRenderer in "Truth Mode".
    """
    print("🚀 Starting UniGrid Truth Mode Test...")
    
    # 1. Setup the "perfect" simulator
    golden = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    golden.seed(get_glider_seed(GRID_WIDTH, GRID_HEIGHT))

    # 2. Setup the renderer with Truth Palette
    renderer = UniGridRenderer(
        width=GRID_WIDTH, 
        height=GRID_HEIGHT, 
        palette_func=Palettes.truth,
        decay_rate=0.0
    )
    renderer_task = asyncio.create_task(renderer.start())

    abs_err = 0

    try:
        for gen in range(MAX_GENERATIONS):
            # A. Get the next "correct" state from the simulator
            theoretical_grid = golden.step()
            
            # B. For this test, assume the "actual" grid from agents is identical
            actual_grid = theoretical_grid.copy()

            # --- Inject a fake error to test colors ---
            # Should turn RED (2.0)
            if 20 <= gen < 40:
                actual_grid[5, 5] = 1 
                abs_err = 1
            
            # Should turn CYAN (3.0)
            if 30 <= gen < 50:
                glider_pos = np.where(theoretical_grid == 1)
                if len(glider_pos[0]) > 0:
                    actual_grid[glider_pos[0][0], glider_pos[1][0]] = 0
                    abs_err = 1

            # C. Encode State
            display_grid = np.zeros(actual_grid.shape, dtype=np.float32)
            display_grid[(actual_grid == 1) & (theoretical_grid == 1)] = 1.0
            display_grid[(actual_grid == 1) & (theoretical_grid == 0)] = 2.0
            display_grid[(actual_grid == 0) & (theoretical_grid == 1)] = 3.0

            # D. Push Frame
            renderer.ingest_full(display_grid)
            renderer.set_extra_info(f"Gen {gen} | Errors: {abs_err}")
            
            # E. Wait
            await asyncio.sleep(FRAME_DELAY)

    finally:
        renderer.stop()
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task
        print("\n✅ Renderer Test Finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
~~~~~

#### Acts 5: 清理

移除不再使用的 `truth/renderer.py`。

~~~~~act
delete_file
observatory/protoplasm/truth/renderer.py
~~~~~

### 下一步建议
我们已经完成了 Protoplasm 阶段所有的基础设施预研。渲染器统一了，通信协议验证了，误差分析完成了。现在，我们拥有了构建“创世网格”所需的所有组件。
建议运行 `python -m observatory.protoplasm.truth.run_conway_experiment` 进行最后的集成测试，确认新的渲染器在实际高负载下的表现。
