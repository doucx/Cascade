好的，基础设施的统一工作已经圆满完成。我们不仅获得了巨大的性能提升，还成功简化了系统的复杂度。

我将首先生成提交计划，随后为你提供一份实验指南。

## [COMMIT] refactor(observatory): 全面统一至裸金属渲染器并移除旧版组件

### 用户需求
将 Observatory 实验室的所有实验脚本统一迁移至高性能的 `RawTerminalApp` 渲染器，并清理过时的、基于 Rich Layout 的渲染组件。

### 评论
通过这次迁移，我们确立了基于字节流的“裸金属”渲染为 Observatory 的标准 UI 方案。这不仅消除了不同实验间的性能差异，还通过恢复 `ingest_grid` 接口确保了对低频事件驱动模拟的完美支持。

### 目标
1.  提交对 `RawTerminalApp` 的功能增强（恢复同步摄入接口）。
2.  提交所有实验脚本（Conway, Bottleneck, Stress Test 等）的迁移修改。
3.  正式删除不再使用的 `observatory/visualization/app.py`。

### 基本原理
统一渲染后端可以显著降低维护成本。删除旧版组件是为了防止未来开发中误用低性能的布局引擎。

### 标签
#intent/refine #flow/ready #priority/medium #comp/observatory #concept/ui #scope/perf #ai/instruct #task/domain/visualization #task/object/raw-renderer #task/action/cleanup #task/state/end

---

### Script

#### Acts 1: 提交重构后的可视化系统与实验脚本

~~~~~act
git_add
observatory/visualization/raw_app.py
observatory/protoplasm/truth/validator.py
observatory/protoplasm/truth/run_conway_experiment.py
observatory/protoplasm/truth/truth_visualizer_demo.py
observatory/protoplasm/governance/bottleneck_sim.py
observatory/protoplasm/renderer/stress_test.py
observatory/visualization/app.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(observatory): unify all experiments under Raw Metal renderer

Completed the migration of all laboratory experiments to the high-performance RawTerminalApp.

Key Changes:
- **RawTerminalApp**: Added `ingest_grid` to support synchronous event-based updates, ensuring compatibility with legacy simulation patterns.
- **Full Migration**: Updated Conway's Game of Life, Validator, Bottleneck Simulator, and Renderer Stress Tests to use the byte-stream pipeline.
- **Cleanup**: Deleted the legacy `app.py` which was based on the slower Rich Layout engine.

This unification provides a consistent 60 FPS (capped) visualization experience across all scientific experiments in the Cascade ecosystem.
~~~~~

---

## 🧪 Observatory 实验实验室使用指南

欢迎来到 Observatory。这里是 Cascade 的物理实验室，所有的实验都已适配**裸金属渲染器 (Raw Metal Renderer)**，提供极致的性能体验。

### 1. 核心模拟 (Visual Experiments)

这些实验提供了完整的 TUI 可视化界面，运行前请确保终端窗口足够大（建议全屏）。

*   **萤火虫同步 (Firefly Sync)**
    *   **命令**: `python -m observatory.experiments.run_fireflies`
    *   **描述**: 模拟 2500+ 个脉冲耦合振荡器。观察系统如何从随机闪烁自发演化为全网呼吸般的同步。
    *   **遥测**: 自动生成 `firefly_log_*.jsonl`，包含 R值、FPS、Jitter 等指标。

*   **因果生命游戏 (Causal Conway)**
    *   **命令**: `python -m observatory.protoplasm.truth.run_conway_experiment`
    *   **描述**: 在异步、分布式的 Agent 网络上运行康威生命游戏。
    *   **验证**: 背后运行着 3-Network 验证模型，实时计算逻辑错误（Red Diff）。

*   **资源瓶颈模拟 (Bottleneck Simulator)**
    *   **命令**: `python -m observatory.protoplasm.governance.bottleneck_sim`
    *   **描述**: 演示 `ConstraintManager` 的威力。
    *   **视觉说明**: 灰色为休眠，**红色**为因资源竞争被阻塞，白色为运行中。你可以实时看到“调度压力波”。

### 2. 性能与验证 (Benchmarking & Demos)

*   **渲染器波浪测试 (Wave Test)**
    *   **命令**: `python -m observatory.protoplasm.renderer.wave_test`
    *   **描述**: 压力测试渲染管线的极限。会根据终端大小自动填充，产生高频色彩波动。

*   **3-Network 验证演示 (Truth Demo)**
    *   **命令**: `python -m observatory.protoplasm.truth.truth_visualizer_demo`
    *   **描述**: 专门演示如何检测逻辑错误（FP/FN）和漂移错误。你可以看到模拟的“幻影细胞”如何被标记为红色。

### 3. 系统底层测试 (Headless Physics)

这些测试不提供 UI，通过命令行输出报告。

*   **时钟抖动测试**: `python -m observatory.protoplasm.physics.jitter_meter`
*   **长生递归测试**: `python -m observatory.protoplasm.physics.recursion_test`
*   **通信性能基准**: `python -m observatory.protoplasm.networking.proto_direct_connect`

### 💡 提示
-   **退出**: 所有实验均支持 `Ctrl+C` 安全退出。
-   **查看日志**: 实验生成的 `.jsonl` 文件可以使用 `grep` 或任何 JSON 工具进行分析。
-   **FPS 锁定**: 默认锁定在 60 FPS 以平衡视觉效果与 CPU。如需修改，请调整 `raw_app.py` 中的 `target_fps`。
