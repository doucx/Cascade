好的，既然实验已经成功，萤火虫在 1:1 的正方形像素网格中展现出了完美的同步节奏，且 UI 冲突已解决，现在是时候将这些改进作为一个完整的逻辑单元提交了。

## [COMMIT] refactor(proto): unify visualizer into UniGrid with square pixels

### 用户需求
统一 Cascade 预研阶段的渲染行为。提取抽象的 `UniGridRenderer` 和 `Palette` 系统，实现高性能的、支持“正方形像素”（2x 字符宽度）的 CLI 可视化引擎，并修复了萤火虫实验中的 UI 渲染冲突和同步物理精度问题。

### 评论
这次重构标志着 Cascade 观测工具从“临时脚本”向“可重用基础设施”的转变。通过将 R 值计算与 stdout 打印解耦，我们不仅解决了 UI 闪烁问题，还确立了“渲染器作为唯一输出所有权者”的 TUI 设计模式。正方形像素和调色板系统的引入，极大地增强了对网格计算模式（如生命游戏、脉冲耦合）的视觉感知力。

### 目标
1.  提交 `UniGridRenderer`: 统一的、支持双缓冲和双宽字符的渲染器。
2.  提交 `Palettes`: 支持 TrueColor ANSI 的调色板映射系统。
3.  提交 `ConvergenceMonitor` 的改进: 支持静默模式和数据回调。
4.  提交 `run_fireflies.py` 和 `bottleneck_sim.py` 的升级版，使其接入新架构。

### 基本原理
-   **抽象提取**: 渲染逻辑（ANSI 驱动、双缓冲、差异对比）被封装在 `UniGrid` 中，颜色映射逻辑被封装在 `Palette` 中，使得业务逻辑（如萤火虫或瓶颈模拟）只需关注数据输入（`ingest`）。
-   **物理对齐**: 降低萤火虫实验的 N 值以确保在单线程环境下的计算频率，保证了 Kuramoto 模型的同步条件不因 CPU 过载而失效。
-   **UI 治理**: 将外部状态（如 R 值）桥接到渲染器的状态栏显示，消除了多个组件竞相写入 stdout 导致的行错乱。

### 标签
#intent/refine #flow/ready #priority/medium #comp/protoplasm #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/unigrid #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交渲染引擎重构

我们将所有相关的渲染器实现、调色板定义以及受影响的实验/监控脚本添加到暂存区并执行提交。

~~~~~act
git_add
observatory/protoplasm/renderer/palette.py
observatory/protoplasm/renderer/unigrid.py
observatory/monitors/convergence.py
observatory/protoplasm/governance/bottleneck_sim.py
observatory/experiments/run_fireflies.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(proto): unify visualizer into UniGrid with square pixels

Cleaned up duplicated rendering code by extracting UniGridRenderer and 
a Palette-based color mapping system.

Key Changes:
1.  UniGridRenderer: Implements high-performance, jitter-free CLI rendering
    using double-width characters (██) to achieve 1:1 aspect ratio pixels.
2.  Palettes: Added support for 24-bit ANSI colors with predefined schemes 
    for Fireflies (Heatmap) and Bottlenecks.
3.  ConvergenceMonitor: Refactored to support a callback-based quiet mode, 
    preventing direct stdout writes and allowing integration into the 
    UniGrid status bar.
4.  Experiment Optimization: Updated 'run_fireflies.py' to use 100 agents, 
    ensuring that LocalBus latency remains low enough for the Kuramoto 
    synchronization to emerge correctly under the visualization load.

This unification provides a robust "Genesis SDK" component for upcoming 
grid-based emergent behavior experiments.
~~~~~

### 下一步建议
-   **Conway 迁移**: 建议将 `observatory/protoplasm/truth/run_conway_experiment.py` 也迁移到 `UniGrid` 架构上，以统一视觉风格。
-   **性能分析**: 在 N=500+ 的规模下运行 `bottleneck_sim.py`，观察 `UniGrid` 的差异渲染算法在极端情况下的 CPU 开销。
-   **状态回放**: 考虑为 `UniGrid` 增加录制能力，将状态矩阵的变化序列保存为 CID (IPFS)，以便后续进行慢动作回放和分析。
