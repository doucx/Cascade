这是一个非常敏锐的洞察。你指出的两个问题击中了要害：

1.  **无效注入 (The "Air Erasure" Bug)**: 我在 T=100 试图擦除 (0,0) 的细胞，但那是空气。滑翔机早就飞远了。而且，只修改返回值而不修改模拟器内部状态，导致错误在下一帧被自动“纠正”（因为模拟器内部还是对的）。
2.  **孤立点死亡 (The "Lonely Death" Problem)**: 注入单个点会导致它在下一帧因“人丁稀少”而死亡。由于 A（实际）和 B（基于 A 的预测）都遵循同一套规则，它们都会让这个点死去。于是，**逻辑错误（红）只存在了一帧**，随后虽然变成了漂移错误（因为 C 里没这个点），但因为点死了（变成 0），而 C 里该位置也是 0，所以 `0 vs 0` 被判定为正确。

**结论**：要看到持久的“漂移错误（金/紫）”，我们需要注入一个**能活下来的错误**（如 2x2 方块），或者杀得死一个**本该活着的结构**。

我将修正 `truth_visualizer_demo.py`，实施“有效打击”。

## [WIP] fix(demo): 修正错误注入逻辑以验证三网模型

### 用户需求
1.  修正 Demo 中的错误注入方式，确保注入的错误能修改模拟器内部状态并持久化。
2.  注入 2x2 方块而非单点，以产生持久的漂移信号。
3.  通过“全屏清空”来确保捕获到“假阴性”错误。

### 评论
之前的测试代码是在“对着空气开枪”。修正后的代码将进行“外科手术式打击”。
- Gen 30: 在空地生成一个 2x2 碉堡 (Block)。这应该产生一帧红色（逻辑突变），随后转为持久的金色（漂移存活）。
- Gen 100: 执行灭绝令（全屏清空）。这应该导致屏幕大面积变青（逻辑缺失），随后部分转为紫色（漂移缺失）。

### 目标
使 `truth_visualizer_demo.py` 正确展示四种错误颜色，验证三网模型的有效性。

### 基本原理
- **Persistence**: 使用 `simulated_cluster.seed(grid_a)` 将修改后的状态回写到模拟器，确保错误传播。
- **Block Injection**: 2x2 方块是 Still Life，不会消失，适合观察 Drift。
- **Extinction**: 全屏清空是验证 Missing 错误的通过性测试。

### 标签
#intent/fix #flow/ready #priority/medium #comp/docs #concept/testing #scope/core #ai/instruct #task/domain/testing #task/object/demo #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 修正 Demo 注入逻辑

~~~~~act
write_file
observatory/protoplasm/truth/truth_visualizer_demo.py
~~~~~
~~~~~python
"""
truth_visualizer_demo.py - 3-Network Validation Demo (Fixed)

This script demonstrates the "A/B/C" validation model.
Network A: Simulated Cluster (with injected errors)
Network B: Step Predictor (Internal to Validator)
Network C: Absolute Truth (Internal to Validator)

Scenarios:
1. Logic Error (FP): Sudden appearance of a block.
   - Frame T: Red (A has it, B doesn't)
   - Frame T+1: Gold (A has it, B predicts it, C doesn't)
2. Logic Error (FN): Sudden disappearance of everything.
   - Frame T: Cyan (A empty, B has life)
   - Frame T+1: Violet (A empty, B predicts empty, C has life)
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
MAX_GENERATIONS = 200
FRAME_DELAY = 0.05

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
        palette_func=Palettes.truth_diff, 
        decay_per_second=0.0
    )
    status_bar = StatusBar({"Generation": 0, "Status": "Init"})
    app = TerminalApp(grid_view, status_bar)

    # 3. Setup Validator
    validator = StateValidator(GRID_WIDTH, GRID_HEIGHT, connector=None, app=app)

    await app.start()
    try:
        # Feed Gen 0
        validator.ingest_full_state(0, seed)
        await asyncio.sleep(1.0) 

        for gen in range(1, MAX_GENERATIONS):
            # --- Step Network A ---
            grid_a = simulated_cluster.step()
            
            # --- Inject Errors ---
            injected = False
            
            # Scenario 1: Gen 30 - The "Bunker" Injection
            # Inject a 2x2 Block (Still Life) at (10, 10).
            # It survives forever.
            if gen == 30:
                grid_a[10:12, 10:12] = 1
                injected = True
                app.update_status("Event", "INJECT: Logic FP (Red Block)")
            
            if gen == 32:
                 app.update_status("Event", "Result: Drift (Gold Block)")

            # Scenario 2: Gen 100 - The "Extinction" Event
            # Wipe out the entire grid.
            if gen == 100:
                grid_a.fill(0)
                injected = True
                app.update_status("Event", "INJECT: Mass Logic FN (Cyan)")

            # CRITICAL FIX: If we modified grid_a, we MUST write it back 
            # to the simulator so the error persists/propagates!
            if injected:
                simulated_cluster.seed(grid_a)

            # --- Validation ---
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

### 下一步建议
现在运行 `python -m observatory.protoplasm.truth.truth_visualizer_demo`。

**预期现象**：
1.  **Gen 0-29**: 白色滑翔机正常飞行。
2.  **Gen 30**: (10,10) 处突然闪现一个 **红色 (Logic FP)** 的 2x2 方块。
3.  **Gen 31+**: 该方块变为 **金色 (Drift FP)** 并一直停留在那里。此时滑翔机继续飞行（如果没撞上方块的话）。
4.  **Gen 100**: 屏幕上所有活着的细胞（滑翔机和金色方块）瞬间变成 **青色 (Logic FN)**。
5.  **Gen 101+**: 
    *   屏幕变黑（因为 A 已经空了，B 预测空 -> 空）。
    *   但是！C（绝对真理）认为滑翔机还在飞。
    *   所以滑翔机原本应该在的位置，会显示出 **紫色 (Drift FN)** 的幽灵影像，沿着 C 的预测路径继续飞行。

这将完美验证 A/B/C 三网模型的全部逻辑分支。
