好的，我们已经成功修复了瓶颈模拟器的核心逻辑，并根据你的要求微调了视觉呈现。这是一个完整且稳固的改进。

现在我将生成一个 `[COMMIT]` 计划，将这些变更作为一个逻辑单元提交。

## [COMMIT] fix(runtime/sim): 修复约束匹配并增强瓶颈模拟器的可观测性

### 用户需求
1.  修复 `ConstraintHandler` 无法处理中间通配符（如 `agent_*_work`）的问题。
2.  增强 Engine 的可观测性，使其能感知并广播因资源竞争导致的阻塞状态。
3.  更新瓶颈模拟器的视觉方案，使用“休眠 (灰)、阻塞 (暗红)、运行 (白)”三态显示。

### 评论
这次修复不仅解决了特定的仿真 bug，还通过引入 `ResourceManager.can_acquire` 预检机制，提升了 Cascade 运行时的通用治理能力，使任何受并发或速率限制的任务都能被外界（如仪表盘）准确地识别为“阻塞”状态，而不仅仅是“运行中”。

### 目标
1.  将所有相关文件的修改提交到 Git 仓库。
2.  确保提交信息清晰描述了从底层匹配逻辑到顶层视觉呈现的完整链路。

### 基本原理
按照 `[COMMIT]` 规范，本计划仅包含 `git_add` 和 `git_commit` 操作。这标志着“瓶颈模拟器修复”这一任务序列的圆满结束。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/cli #concept/governance #concept/ui #scope/core #scope/ux #ai/instruct #task/domain/governance #task/object/bottleneck-sim #task/action/fix-and-refine #task/state/end

---

### Script

#### Acts 1: 提交瓶颈模拟器相关的逻辑与视觉修复

我们将把修改后的运行时核心代码、可视化组件以及实验脚本添加到暂存区。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
packages/cascade-runtime/src/cascade/runtime/engine.py
observatory/visualization/palette.py
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime/sim): fix constraint matching and improve observability in bottleneck simulation

This commit addresses the issue where the bottleneck simulator failed to reflect task blocking.

Key changes:
- Logic: Refactored 'ConstraintHandler' to use 'fnmatch' for robust scope matching, supporting complex wildcard patterns like 'agent_*_work'.
- Engine: Added 'can_acquire' to 'ResourceManager' and updated 'Engine' to proactively publish 'TaskBlocked' events upon resource contention, enabling real-time visibility into queued tasks.
- Visuals: Updated 'bottleneck' palette with a new 3-state encoding: Sleeping (Grey), Blocked (Dark Red), and Running (White).
- Simulation: Improved 'bottleneck_sim.py' workflow and event handling to leverage new telemetry events for accurate agent state tracking and counter reporting.

This significantly enhances the diagnostic capabilities of the Cascade runtime under resource-constrained scenarios.
~~~~~

### 下一步建议
- **压力测试**: 现在你可以运行 `python -m observatory.protoplasm.governance.bottleneck_sim`，你应该能看到大量 Agent 在进入“暗红色”阻塞状态后，有序地获得资源并转为“白色”运行状态。
- **扩展观测**: 你可以尝试启动 `cs-observer`，验证 `TaskBlocked` 事件是否也能在标准遥测流中被正确捕获和显示。
