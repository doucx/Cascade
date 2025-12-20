这是一个非常严谨且具有高度可观测性的验证方案。

 可行性分析

你的方案不仅可行，而且从分布式系统测试的角度来看，这是一个**黄金标准 (Gold Standard)** 的设计。

1.  **三网模型 (The 3-Network Model)** 的引入完美地区分了两种不同性质的错误：
    *   **相对误差 (vs B)**: 验证**规则执行的正确性**。如果 A 与 B 不一致，说明当前这一步计算错了（例如：比特翻转、逻辑 Bug）。这是**红色警报**。
    *   **绝对误差 (vs C)**: 验证**系统的一致性与收敛性**。如果 A 与 C 不一致，但在 B 上一致，说明 A 当前计算是符合逻辑的，但它处于一个**错误的时间线**上（例如：之前的某一步丢包了，导致后续所有演化都偏离了创世种子的预期）。这是**黄色警报**。

2.  **UI/逻辑解耦**:
    *   通过将 Validator 设计为核心逻辑单元，`truth_visualizer_demo` 变成了一个单纯的“故障注入模拟器”，而 `run_conway_experiment` 则是“真实环境运行器”。两者共享完全相同的验证逻辑和渲染管线，确保了测试工具本身的可靠性。

 颜色定义

为了清晰区分四种错误类型（假阳性/假阴性 x 逻辑/漂移），我们定义以下配色方案：

1.  **正确 (Correct)**
    *   **Dead**: 暗灰 (Dim Gray) `rgb(40,40,40)`
    *   **Alive**: 亮白 (White) `rgb(220,220,220)`

2.  **逻辑错误 (Logic Error) - 相对于 B (上一刻的 A)**
    *   *优先级最高，代表当前计算出错。*
    *   **假阳性 (Ghost)** (A=1, B=0): **亮红 (Bright Red)** `rgb(255,50,50)` - "不该活的活了"
    *   **假阴性 (Missing)** (A=0, B=1): **青色 (Cyan)** `rgb(0,255,255)` - "该活的死了"

3.  **漂移错误 (Drift Error) - 相对于 C (创世种子)**
    *   *优先级次之，代表处于错误的时间线。*
    *   **假阳性 (Drift Ghost)** (A=1, C=0): **金黄 (Gold)** `rgb(255,215,0)` - "历史偏差导致的幽灵"
    *   **假阴性 (Drift Missing)** (A=0, C=1): **紫罗兰 (Violet)** `rgb(238,130,238)` - "历史偏差导致的缺失"

---

 计划概要

我将执行以下计划：

1.  **更新调色板 (`palette.py`)**: 实现上述 6 种状态的颜色映射。
2.  **重构验证器 (`validator.py`)**: 
    *   引入 `GoldenLife` 的两个实例：`golden_absolute` (C) 和 `golden_relative` (B)。
    *   实现三方对比逻辑，生成包含 0-5 状态码的 Diff 矩阵。
    *   增加 `ingest_full_state` 方法，允许 Demo 直接注入完整状态，绕过消息总线拼接。
3.  **重写 Demo (`truth_visualizer_demo.py`)**:
    *   模拟 Network A（带故障注入）。
    *   直接调用 Validator 进行验证和渲染。
4.  **适配实验脚本 (`run_conway_experiment.py`)**: 确保其适配新的 Validator 接口。

这将彻底解决“先白后红”的闪烁问题，因为状态在渲染前就已经被 Validator 解析为“错误”了。

## [WIP] feat(proto): 实现三网验证模型 (A/B/C) 与高级差分可视化

### 摘要头
## [WIP] feat(proto): 实现三网验证模型 (A/B/C) 与高级差分可视化

### 用户需求
1.  构建一个三层验证模型：A(实际)、B(相对预测)、C(绝对预测)。
2.  在可视化中区分逻辑错误（红/青）和漂移错误（黄/紫）。
3.  重构 `validator.py` 以支持该逻辑，并使 `demo` 和 `experiment` 共享此核心。

### 评论
这是一个架构级的改进。它将验证器的职责从简单的“找茬”提升到了“诊断”。通过区分 B 和 C，我们可以立即知道系统是仅仅“这一步算错了”，还是“已经彻底偏离了航道”。依赖注入模式的使用也极大地提高了测试工具的可信度。

### 目标
1.  修改 `Palettes.truth_diff` 支持 6 种状态颜色。
2.  重构 `StateValidator` 类，维护两个 `GoldenLife` 实例，并实现优先级的 Diff 逻辑。
3.  更新 `truth_visualizer_demo.py` 使用新的验证器接口。
4.  确保 `run_conway_experiment.py` 兼容。

### 基本原理
我们利用 Numpy 的向量化操作来高效计算 Diff 矩阵。
优先级逻辑：`Mask_Logic_Error` 覆盖 `Mask_Drift_Error`。
- Logic Diff: `A != B`
- Drift Diff: `A != C` (仅在 `A == B` 时显示)

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/history #scope/core #ai/instruct #task/domain/testing #task/object/validator #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新调色板

我们首先定义新的颜色映射方案。

~~~~~act
patch_file
observatory/visualization/palette.py
~~~~~
~~~~~python
    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors.
        0: Dead (Correct) -> Dark Gray
        1: Alive (Correct) -> Bright White
        2: False Positive (Ghost) -> Bright Red
        3: False Negative (Missing) -> Bright Cyan
        """
        colors = np.full(diff_matrix.shape, "rgb(40,40,40)", dtype="<U18") # Default to dead
        colors[diff_matrix == 1] = "rgb(220,220,220)" # Alive
        colors[diff_matrix == 2] = "rgb(255,50,50)"   # False Positive
        colors[diff_matrix == 3] = "rgb(50,220,255)"   # False Negative
        return colors
~~~~~
~~~~~python
    @staticmethod
    def truth_diff(diff_matrix: np.ndarray) -> np.ndarray:
        """
        Maps a diff matrix to validation colors (3-Network Model).
        
        0: Dead (Correct)          -> Dim Gray
        1: Alive (Correct)         -> Bright White
        
        Logic Errors (vs Step Prediction):
        2: FP (Logic Ghost)        -> Bright Red
        3: FN (Logic Missing)      -> Cyan
        
        Drift Errors (vs Absolute Truth):
        4: FP (Drift Ghost)        -> Gold
        5: FN (Drift Missing)      -> Violet
        """
        # Default: 0 (Dead/Correct)
        colors = np.full(diff_matrix.shape, "rgb(40,40,40)", dtype="<U18")
        
        colors[diff_matrix == 1] = "rgb(220,220,220)" # Alive (Correct)
        colors[diff_matrix == 2] = "rgb(255,50,50)"   # Logic FP (Red)
        colors[diff_matrix == 3] = "rgb(0,255,255)"   # Logic FN (Cyan)
        colors[diff_matrix == 4] = "rgb(255,215,0)"   # Drift FP (Gold)
        colors[diff_matrix == 5] = "rgb(238,130,238)" # Drift FN (Violet)
        
        return colors
~~~~~

#### Acts 2: 重构验证器核心逻辑

我们将 `StateValidator` 升级为支持 A/B/C 三网模型。我们添加了 `ingest_full_state` 方法来支持 Demo 的直接调用。

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
from observatory.visualization.app import TerminalApp

class StateValidator:
    """
    Implements the 3-Network Validation Model:
    Network A: Actual State (from Telemetry or Simulation)
    Network B: Relative Truth (Stepwise prediction based on A[t-1])
    Network C: Absolute Truth (Pathfinding based on Initial Seed)
    """
    def __init__(self, width: int, height: int, connector: Connector, app: Optional[TerminalApp] = None):
        self.width = width
        self.height = height
        self.connector = connector
        self.app = app
        
        # Network B: Relative Predictor (Resets every gen)
        self.golden_relative = GoldenLife(width, height)
        
        # Network C: Absolute Truth (Persists)
        self.golden_absolute = GoldenLife(width, height)
        
        # Internal Diff Matrix for rendering (0-5 states)
        self.diff_matrix = np.zeros((height, width), dtype=np.int8)
        
        # Buffers for Async Aggregation
        self.buffer: Dict[int, Dict[int, int]] = {}
        self.history_actual: Dict[int, np.ndarray] = {}
        
        self.total_agents = width * height
        self._running = False
        
        # Stats
        self.stats = {
            "logic_errors": 0, # A != B
            "drift_errors": 0  # A != C
        }
        self.max_gen_verified = -1

    async def run(self):
        """Async listener loop for the real experiment."""
        self._running = True
        if not self.app:
            print(f"⚖️  Validator active (headless). Grid: {self.width}x{self.height}.")
        
        sub = await self.connector.subscribe("validator/report", self.on_report)
        try:
            while self._running:
                self._process_buffers()
                await asyncio.sleep(0.01)
        finally:
            await sub.unsubscribe()

    async def on_report(self, topic: str, payload: Any):
        """Collects async reports from agents."""
        gen = payload['gen']
        agent_id = payload['id']
        
        if gen not in self.buffer:
            self.buffer[gen] = {}
        self.buffer[gen][agent_id] = payload

    def _process_buffers(self):
        """Checks if we have a full frame to verify."""
        next_gen = self.max_gen_verified + 1
        
        if next_gen not in self.buffer:
            if self.app and next_gen > 0:
                 self._update_progress_ui(next_gen, 0)
            return

        current_buffer = self.buffer[next_gen]
        
        if len(current_buffer) < self.total_agents:
            if self.app:
                self._update_progress_ui(next_gen, len(current_buffer))
            return
            
        # Reconstruct full grid A
        actual_grid = np.zeros((self.height, self.width), dtype=np.int8)
        for r in current_buffer.values():
            x, y = r['coords']
            actual_grid[y, x] = r['state']
            
        # Verify
        self.ingest_full_state(next_gen, actual_grid)
        
        # Cleanup
        del self.buffer[next_gen]
        # Keep minimal history for Relative prediction
        if next_gen - 2 in self.history_actual:
            del self.history_actual[next_gen - 2]
            
        self.max_gen_verified = next_gen

    def _update_progress_ui(self, gen, count):
        bar_len = 20
        progress = count / self.total_agents
        filled = int(bar_len * progress)
        bar = "█" * filled + "░" * (bar_len - filled)
        self.app.update_status("Progress", f"Gen {gen}: [{bar}]")

    def ingest_full_state(self, gen: int, grid_a: np.ndarray):
        """
        Direct entry point for validation. 
        Can be called by _process_buffers (Async) or directly by Demo (Sync).
        """
        # Store A for future B predictions
        self.history_actual[gen] = grid_a.copy()

        # --- 1. Compute Network C (Absolute Truth) ---
        if gen == 0:
            self.golden_absolute.seed(grid_a)
            grid_c = grid_a # At gen 0, C is defined by A
        else:
            # C steps forward from its own internal state
            grid_c = self.golden_absolute.step()

        # --- 2. Compute Network B (Relative Truth) ---
        if gen == 0:
            grid_b = grid_a # At gen 0, B is defined by A
        else:
            # B steps forward from A's LAST state
            prev_a = self.history_actual.get(gen - 1)
            if prev_a is not None:
                self.golden_relative.seed(prev_a)
                grid_b = self.golden_relative.step()
            else:
                # Should not happen in sequential exec, fallback to C
                grid_b = grid_c

        # --- 3. Compute Diff Matrix ---
        self._compute_diff(grid_a, grid_b, grid_c)
        
        # --- 4. Update UI ---
        if self.app:
            self.app.ingest_full_matrix(self.diff_matrix)
            self.app.update_status("Generation", gen)
            
            logic_err = np.sum((grid_a != grid_b))
            drift_err = np.sum((grid_a != grid_c))
            
            self.stats["logic_errors"] += logic_err
            self.stats["drift_errors"] += drift_err
            
            status_icon = "✅ SYNC" if (logic_err + drift_err) == 0 else "❌ ERROR"
            self.app.update_status("Status", status_icon)
            self.app.update_status("Logic Err", f"{logic_err} (Cum: {self.stats['logic_errors']})")
            self.app.update_status("Drift Err", f"{drift_err} (Cum: {self.stats['drift_errors']})")

    def _compute_diff(self, A: np.ndarray, B: np.ndarray, C: np.ndarray):
        """
        Generates the visualization mask.
        Priority: Logic Error (vs B) > Drift Error (vs C) > Correct
        """
        self.diff_matrix.fill(0) # Default Dead
        
        # 1. Base Correct State (Matches A)
        self.diff_matrix[A == 1] = 1 
        
        # 2. Drift Errors (A vs C) - Warning Level
        # FP: A=1, C=0 -> 4 (Gold)
        mask_drift_fp = (A == 1) & (C == 0)
        self.diff_matrix[mask_drift_fp] = 4
        
        # FN: A=0, C=1 -> 5 (Violet)
        mask_drift_fn = (A == 0) & (C == 1)
        self.diff_matrix[mask_drift_fn] = 5
        
        # 3. Logic Errors (A vs B) - Critical Level (Overwrites Drift)
        # FP: A=1, B=0 -> 2 (Red)
        mask_logic_fp = (A == 1) & (B == 0)
        self.diff_matrix[mask_logic_fp] = 2
        
        # FN: A=0, B=1 -> 3 (Cyan)
        mask_logic_fn = (A == 0) & (B == 1)
        self.diff_matrix[mask_logic_fn] = 3

    def stop(self):
        self._running = False
~~~~~

#### Acts 3: 更新 Demo 程序

我们将 Demo 更新为使用 3-Network 模型。我们使用 `validator.ingest_full_state` 直接驱动验证，从而消除了闪烁。

~~~~~act
write_file
observatory/protoplasm/truth/truth_visualizer_demo.py
~~~~~
~~~~~python
"""
truth_visualizer_demo.py - 3-Network Validation Demo

This script demonstrates the "A/B/C" validation model.
Network A: Simulated Cluster (with injected errors)
Network B: Step Predictor (Internal to Validator)
Network C: Absolute Truth (Internal to Validator)

It directly drives the StateValidator to visualize:
- Logic Errors (Red/Cyan): A diverges from B (Immediate computation error)
- Drift Errors (Gold/Violet): A matches B, but diverges from C (Wrong timeline)
"""
import asyncio
import numpy as np

from observatory.protoplasm.truth.golden_ca import GoldenLife
from observatory.protoplasm.truth.validator import StateValidator
from observatory.visualization.app import TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar
from observatory.visualization.palette import Palettes

# --- Test Configuration ---
GRID_WIDTH = 50
GRID_HEIGHT = 25
MAX_GENERATIONS = 300
FRAME_DELAY = 0.1

def get_glider_seed(width: int, height: int) -> np.ndarray:
    grid = np.zeros((height, width), dtype=np.int8)
    # Glider at (1,1)
    grid[1, 2] = 1
    grid[2, 3] = 1
    grid[3, 1:4] = 1
    return grid

async def main():
    print("🚀 Starting 3-Network Validation Demo...")
    
    # 1. Network A (The "Actual" System we are simulating)
    simulated_cluster = GoldenLife(GRID_WIDTH, GRID_HEIGHT)
    seed = get_glider_seed(GRID_WIDTH, GRID_HEIGHT)
    simulated_cluster.seed(seed)

    # 2. Setup UI
    grid_view = GridView(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        palette_func=Palettes.truth_diff, # New 6-color palette
        decay_per_second=0.0
    )
    status_bar = StatusBar({"Generation": 0, "Status": "Init"})
    app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator (It holds Network B and C internally)
    # We pass None for connector as we will inject state manually
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector=None, app=app)

    await app.start()
    try:
        # Feed Gen 0
        validator.ingest_full_state(0, seed)
        await asyncio.sleep(1.0) # Pause to see seed

        for gen in range(1, MAX_GENERATIONS):
            # --- Step Network A ---
            grid_a = simulated_cluster.step()
            
            # --- Inject Errors into A ---
            
            # Scenario 1: Logic Error (Flash in the pan) at Gen 30
            # A single cell flips wrongly, but A continues computing correctly from that error.
            # This causes an immediate Red/Cyan flash (Logic Error).
            # Then, because A's state is now physically different, it will drift from C.
            if gen == 30:
                # Inject a False Positive (Ghost)
                grid_a[10, 10] = 1 
                app.update_status("Event", "INJECT: Logic FP (Red)")
            
            if gen == 31:
                 app.update_status("Event", "Result: Drift (Gold)")

            # Scenario 2: Massive Logic Failure at Gen 100
            # A whole block fails to compute
            if gen == 100:
                grid_a[0:5, 0:5] = 0
                app.update_status("Event", "INJECT: Mass Logic FN (Cyan)")

            # --- Validation ---
            # We push A's state to the validator. 
            # It compares A vs B (Relative) and A vs C (Absolute).
            # It calculates the colors and updates the App.
            validator.ingest_full_state(gen, grid_a)
            
            # --- Render Speed Control ---
            await asyncio.sleep(FRAME_DELAY)

    finally:
        app.stop()
        print("\n✅ Demo Finished.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
~~~~~

#### Acts 4: 适配实验脚本

`run_conway_experiment.py` 需要微小的调整来适配新的导入路径和验证器初始化（虽然初始化参数没变，但确保一致性是个好习惯）。

~~~~~act
patch_file
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~
~~~~~python
    # 3. Setup Validator (now accepts the app)
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, app=app)

    # 4. Setup Engine
~~~~~
~~~~~python
    # 3. Setup Validator (Using the new 3-Network Model)
    # It will automatically maintain Relative (B) and Absolute (C) truth chains.
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector, app=app)

    # 4. Setup Engine
~~~~~

### 下一步建议
运行 `python -m observatory.protoplasm.truth.truth_visualizer_demo` 验证新的三网模型和色彩逻辑。你应该能看到滑翔机正常运行，直到第 30 代出现一个红点（逻辑错误），随后该点变为金黄色（漂移错误），并在第 100 代看到大片的青色区域（逻辑缺失）。
