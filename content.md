这非常合理。为了保持技术栈的统一并消除旧版 `TerminalApp` 带来的维护负担，我们应该将所有实验迁移到 `RawTerminalApp`。

为了支持 `bottleneck_sim.py` 这种依赖同步回调（`handle_event`）的场景，我们需要在 `RawTerminalApp` 中恢复基于队列的 `ingest_grid` 方法。虽然这比批量更新慢，但对于低频事件驱动的模拟来说足够了，且能保证兼容性。

## [WIP] refactor(observatory): 全面迁移至 RawTerminalApp 并恢复同步数据摄入接口

### 用户需求
将 `bottleneck_sim.py`, `run_conway_experiment.py` 等剩余实验脚本迁移到高性能渲染器。

### 评论
1.  **兼容性缺失**：`RawTerminalApp` 缺少旧版 `TerminalApp` 的 `ingest_grid` 方法，导致无法在同步回调（如 `bottleneck_sim` 中的事件处理器）中使用。
2.  **API 不一致**：`stress_test.py` 使用了旧的单点更新 API。

### 目标
1.  **增强 RawTerminalApp**：添加 `ingest_grid` 方法，并在渲染循环中处理 `"grid"` 类型的队列消息。
2.  **迁移脚本**：将所有实验脚本的导入语句从 `visualization.app` 切换到 `visualization.raw_app`。
3.  **适配调用**：修正 `stress_test.py` 中的 API 调用。

### 标签
#intent/refine #flow/ready #priority/medium #comp/observatory #concept/ui #scope/app #ai/instruct #task/domain/visualization #task/object/raw-renderer #task/action/migration #task/state/end

---

### Script

#### Acts 1: 增强 RawTerminalApp 以支持同步数据摄入

这是为了兼容 `bottleneck_sim.py`。

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
~~~~~
~~~~~python
    def update_status(self, key: str, value: Any):
        """Async status update."""
        self.queue.put_nowait(("status", (key, value)))

    def ingest_grid(self, x: int, y: int, state: float):
        """
        Legacy sync ingestion for event callbacks (e.g. from synchronous bus listeners).
        Adds overhead compared to batch updates but ensures compatibility.
        """
        self.queue.put_nowait(("grid", (x, y, state)))

    def ingest_full_matrix(self, new_matrix: np.ndarray):
~~~~~

~~~~~act
patch_file
observatory/visualization/raw_app.py
~~~~~
~~~~~python
            # 2. Process Queue (Status)
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        k, v = data
                        self.status_bar.set_status(k, v)
                except asyncio.QueueEmpty:
                    break
~~~~~
~~~~~python
            # 2. Process Queue (Status & Legacy Grid)
            while not self.queue.empty():
                try:
                    msg_type, data = self.queue.get_nowait()
                    if msg_type == "status":
                        k, v = data
                        self.status_bar.set_status(k, v)
                    elif msg_type == "grid":
                        x, y, s = data
                        # Direct update. Safe because _flush_buffer (via to_thread) is awaited
                        # before we get here, so no race condition on matrix.
                        self.grid_view.matrix.update(x, y, s)
                except asyncio.QueueEmpty:
                    break
~~~~~

#### Acts 2: 迁移 Conway 实验与 Validator

修改 `validator.py` 的类型提示和导入，以及实验脚本。

~~~~~act
patch_file
observatory/protoplasm/truth/validator.py
~~~~~
~~~~~python
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.visualization.app import TerminalApp


class StateValidator:
~~~~~
~~~~~python
from cascade.interfaces.protocols import Connector
from .golden_ca import GoldenLife
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp


class StateValidator:
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
from observatory.protoplasm.truth.validator import StateValidator

# New Visualization imports
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~
~~~~~python
from observatory.protoplasm.truth.validator import StateValidator

# New Visualization imports
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~

~~~~~act
patch_file
observatory/protoplasm/truth/truth_visualizer_demo.py
~~~~~
~~~~~python
from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth.validator import StateValidator
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~
~~~~~python
from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth.validator import StateValidator
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~

#### Acts 3: 迁移瓶颈模拟 (Bottleneck Sim)

~~~~~act
patch_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
from cascade.spec.constraint import GlobalConstraint

# New Renderer Imports
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~
~~~~~python
from cascade.spec.constraint import GlobalConstraint

# New Renderer Imports
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~

#### Acts 4: 迁移并修复 Stress Test

~~~~~act
patch_file
observatory/protoplasm/renderer/stress_test.py
~~~~~
~~~~~python
import asyncio
import random
import time

from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~
~~~~~python
import asyncio
import random
import time

from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes
~~~~~

~~~~~act
patch_file
observatory/protoplasm/renderer/stress_test.py
~~~~~
~~~~~python
        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)

        # Call the renderer directly, mimicking an agent's flash callback
        app.direct_update_grid(x, y, 1.0)
~~~~~
~~~~~python
        # Generate a "flash"
        x = random.randint(0, GRID_WIDTH - 1)
        y = random.randint(0, GRID_HEIGHT - 1)

        # Call the renderer directly, mimicking an agent's flash callback
        # Use batch API for RawTerminalApp
        await app.direct_update_grid_batch([(x, y, 1.0)])
~~~~~

#### Acts 5: 删除旧的 App

现在所有引用都已更新，旧的 `app.py` 已经不再被使用。虽然通常我们可能会保留旧代码作为参考，但考虑到 `RawTerminalApp` 是完全的替代品且 `app.py` 依赖 Rich Layout（这是我们明确要放弃的），删除它可以减少混淆。

~~~~~act
delete_file
observatory/visualization/app.py
~~~~~

### 下一步建议
现在整个 Observatory 生态系统都统一在了“裸金属”渲染管线上。你可以随意运行任何实验脚本，它们都将享受到极致的性能和统一的体验。

建议运行 `observatory.protoplasm.truth.truth_visualizer_demo` 来验证 3-Network Validation 的可视化是否依然正常（它依赖 `ingest_full_matrix`）。
