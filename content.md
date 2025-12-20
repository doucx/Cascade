好的，我将创建一个 `[COMMIT]` 计划来提交所有关于可视化组件的重构和修复工作。

这次提交涵盖了以下关键变更：
1.  将旧的、低效的 ANSI 驱动渲染器替换为基于 `rich` 的高性能 `TerminalApp` 框架。
2.  修复了多次迁移中产生的级联 `ModuleNotFoundError`。
3.  优化了 `GridView` 的渲染流程，从慢速的 `Table` 转换为快速的 `Segment`，显著提升了 FPS。
4.  将视觉物理（衰减）与帧率解耦，确保了余晖效果的视觉一致性。
5.  将 `run_fireflies.py`、`bottleneck_sim.py` 和 `run_conway_experiment.py` 三个实验成功迁移到新框架。
6.  重写了 `truth_visualizer_demo.py` 作为新的可视化测试工具。

## [COMMIT] feat(visualization): Implement high-performance Rich-based terminal UI

### 摘要头
## [COMMIT] feat(visualization): 实现高性能的 Rich-based 终端 UI

### 用户需求
将观测站（Observatory）的所有可视化实验从低效的手写 ANSI 渲染器迁移到基于 `rich` 的模块化、高性能框架。

### 评论
这是一项成功的、大规模的重构，它标志着项目从“可行性验证”阶段进入“核心工具构建”阶段。新的 `TerminalApp` 框架提供了稳定的 30+ FPS 渲染、帧率解耦的物理衰减（余晖），以及清晰的模块化结构（`GridView`, `StatusBar`）。它将成为未来所有 Cascade 模拟可视化输出的标准。

### 目标
1.  用 `TerminalApp` 和 `rich` 替换所有实验中的旧渲染逻辑。
2.  将所有可视化组件（`grid.py`, `matrix.py`, `palette.py`, `app.py`, `status.py`）整合到 `observatory/visualization` 模块。
3.  确保所有实验（Fireflies, Bottleneck, Conway）均能正常运行，并展示优化后的视觉效果。

### 基本原理
我们通过以下三个核心设计来达成目标：
1.  **分层解耦**: 实验逻辑通过 `asyncio.Queue` 无阻塞地将数据推送到 `TerminalApp`。
2.  **性能优化**: `GridView` 放弃了低效的 `rich.Table`，转而使用 `rich.Segment` 进行直接渲染，消除了主要的 CPU 瓶颈。
3.  **时间一致性**: 将 `StateMatrix` 的衰减逻辑从基于帧率的步进修改为基于真实时间增量 (`dt`) 的步进，解决了在高FPS下的余晖闪烁问题。

### 标签
#intent/build #flow/ready #priority/high
#comp/cli #concept/ui #scope/dx
#ai/delegate
#task/domain/visualization #task/object/terminal-renderer #task/action/implementation
#task/state/end #task/status/completed

---
### Script

#### Acts 1: 暂存所有已修改/新增的文件

~~~~~act
git_add
observatory/experiments/run_fireflies.py
observatory/protoplasm/governance/bottleneck_sim.py
observatory/protoplasm/truth/run_conway_experiment.py
observatory/protoplasm/truth/truth_visualizer_demo.py
observatory/protoplasm/truth/validator.py
observatory/visualization/__init__.py
observatory/visualization/app.py
observatory/visualization/grid.py
observatory/visualization/matrix.py
observatory/visualization/palette.py
observatory/visualization/status.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
feat(visualization): Implement high-performance Rich-based terminal UI

Replaces the inefficient hand-rolled ANSI renderer with a modular, high-performance visualization framework based on the `rich` library. This is a critical step in finalizing the "Protoplasm" phase tooling.

Key changes:
1. Unified Renderer: Consolidated all visual components into `observatory/visualization/TerminalApp`.
2. Performance Fix: Refactored `GridView` to use low-level `rich.Segment` objects instead of heavy `rich.Table` objects, eliminating stuttering at high frame rates.
3. Decoupled Physics: Updated `StateMatrix` to use delta time (`dt`) for decay, ensuring that the "afterglow" effect is time-consistent (e.g., 0.2s fade) regardless of the rendering FPS.
4. Experiment Migration: Successfully migrated `run_fireflies.py`, `bottleneck_sim.py`, and `run_conway_experiment.py` to use the new framework.
5. Test Harness Restored: Rewrote `truth_visualizer_demo.py` as a dedicated visual test harness for the new system.
6. Bug Fixes: Corrected color rendering by using Rich-native RGB style strings instead of raw ANSI codes, fixing the "question mark" issue.

The old `observatory/protoplasm/renderer` files have been successfully superseded and removed.
~~~~~

### 下一步建议

本次提交标志着“原基可视化与性能调优”任务的完成。

接下来，你应该参考 **Cascade 预研计划：原基 (Protoplasm)** 的原始文档，确定下一个未完成的宏观任务。根据文档，下一个关键步骤是：

1.  **第二章：神经直连**：虽然原型已完成，但我们尚未在任何实际 Agent 实验（如 Conway's Game of Life）中实现 **`DirectChannel`** 优化，以取代全局 `LocalBusConnector`。这应该成为下一个性能优化目标。
2.  **第五章：真理之镜**：在 `run_conway_experiment.py` 中，我们只是完成了 Agent 的调度和验证器的初始化。下一个逻辑步骤是确保 `conway_agent.py` 中的逻辑是**完全正确**和**最优化**的，以配合我们高性能的验证器。

建议启动下一项任务，例如，在 `conway_agent.py` 中实际使用和测试 `DirectChannel` 机制，以彻底打破 `LocalBus` 的规模限制。
