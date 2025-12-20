好的，我们已经成功验证了资源约束模拟器和阻塞状态的可视化。现在，我将创建一个 `[COMMIT]` 计划来整合所有这些新功能。

## [COMMIT] feat(runtime): 实现约束模拟与阻塞状态的可观测性

### 用户需求
我们需要一个可靠的方法来压力测试 Cascade 引擎的调度器在高资源竞争下的行为，并能够直观地观测到任务的“阻塞”状态。

### 评论
这是一个关键的里程碑，它证实了 Cascade 核心调度物理学的正确性。通过成功模拟和可视化资源争用，我们验证了 `ResourceManager` 和 `ConstraintManager` 的反压机制是健壮且符合预期的。

本次开发引入的 `TaskBlocked` 事件和约束处理器中的通配符匹配功能，极大地增强了系统的可观测性和控制灵活性，为未来更复杂的调度策略奠定了基础。

### 目标
创建一个单一、完整的 Git 提交，将所有与资源约束模拟和阻塞状态观测相关的代码变更整合到主代码库中。

### 基本原理
该功能现已开发、测试并成功运行。将其作为一个原子提交进行合并，可以保持项目历史的清晰和逻辑完整性，标志着“原基 (Protoplasm)”预研计划第四章的正式完成。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #scope/api #ai/instruct #task/domain/simulation #task/object/resource-constraint #task/action/stress-test #task/state/continue

---

### Script

#### Acts 1: 提交所有相关变更

我们将所有已修改和新建的文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-py/src/cascade/__init__.py
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-runtime/src/cascade/runtime/events.py
packages/cascade-runtime/src/cascade/runtime/subscribers.py
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement constraint simulation and blocked state observability

This commit introduces a comprehensive suite of features to simulate and observe resource contention within the Cascade engine, fulfilling a key objective of the "Protoplasm" pre-research phase.

Key additions:
1.  **`TaskBlocked` Event**: A new `TaskBlocked` event is added to `runtime.events` to represent the state where a task is ready but deferred due to resource constraints.

2.  **Engine Emission**: The `Engine`'s main scheduling loop in `_execute_graph` is updated to detect when tasks are deferred and emit the `TaskBlocked` event. A debouncing mechanism is included to prevent event flooding on repeated deferrals.

3.  **Wildcard Constraint Matching**: The `ConcurrencyConstraintHandler` and `PauseConstraintHandler` now support wildcard matching (e.g., `task:agent_*`) in their scope definitions, allowing for more flexible and powerful constraint application across groups of dynamically named tasks.

4.  **Telemetry Support**: `TelemetrySubscriber` is updated to recognize and serialize `TaskBlocked` events, ensuring this critical state is observable in remote monitoring tools.

5.  **Bottleneck Simulator**: A new experiment, `bottleneck_sim.py`, has been created. It demonstrates a single-engine, multi-agent topology where hundreds of agents compete for a limited number of concurrency slots, with a real-time CLI visualizer rendering the `RUNNING` vs. `BLOCKED` states.

6.  **API Fix**: `cs.Event` is now exposed in the top-level `cascade` namespace, fixing an `AttributeError` and enabling wildcard event subscriptions for monitoring tools.
~~~~~

### 下一步建议
我们已经完成了第四章“压力的具象化”。根据“原基 (Protoplasm)”计划，下一步是 **第五章：真理之镜**。

这要求我们：
1.  **构建一个黄金参考 (Golden Reference)**：一个不依赖 Cascade 的、绝对正确的同步计算模型（例如，一个基于 `numpy` 的康威生命游戏实现）。
2.  **实现一个快照验证协议**：创建一个 `ValidatorActor`，它能从 Cascade 的运行环境中（如 Redis）收集 Agent 的状态快照，并与黄金参考的计算结果进行逐代对比，实时报告任何“红色差异 (Red Diff)”。

这将是对 Cascade 在异步、分布式环境下维持计算**强一致性**能力的终极考验。如果你同意，我将开始着手设计这个验证系统。
