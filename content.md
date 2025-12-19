这是一个关键的里程碑，标志着我们对 Agent 架构和 Engine 并发模型的深度理解。我将为您创建一个 `[COMMIT]` 计划，将这次探索的所有成果和修复提交到历史记录中。

## [COMMIT] feat(observatory): Integrate Firefly Agent, Monitor, and critical fixes

### 用户需求
提交所有为“萤火测试”实现的 Agent 逻辑、观测站工具，以及在调试过程中发现并修复的 Engine 核心调度问题和 Agent 逻辑缺陷。

### 评论
本次提交集成了 Cascade 历史上最复杂的 Agent 模式，同时修复了三个核心架构问题：
1.  **TCO 调度死锁**: 修复 `Engine.run` 中的 TCO 循环，强制让出执行权。
2.  **资源注入缺陷**: 通过显式参数传递，绕过了 `cs.inject` 在深度递归/跨引擎场景下的失效问题。
3.  **图构建陷阱**: 通过显式参数传递，确保 `GraphBuilder` 不会剪枝掉副作用节点。
4.  **物理模型修正**: 修复了 Agent 在接收信号后，相位计算中忽略时间流逝的物理学错误。

这次的测试虽然没有实现完美的同步，但其作为架构验证的价值已经完全实现。

### 目标
将所有与 Agent 实验相关的代码和 Engine 核心修复，作为一个完整的、可验证的工作单元提交。

### 基本原理
所有文件系统更改已经通过先前的 `[WIP]` 计划完成。现在，它们构成了一个逻辑完整的集合，应该被合并到一个单一的 Git 提交中，以确保历史记录的清晰和原子性。

### 标签
#intent/tooling #intent/fix #intent/build #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #scope/dx #ai/refine #task/domain/testing #task/object/firefly-agent #task/action/integration #task/state/end

---

### Script

#### Acts 1: 添加所有修改后的文件到暂存区

将所有涉及 Engine 修复、Agent 逻辑和 Observatory 工具链的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/engine.py
observatory/__init__.py
observatory/agents/__init__.py
observatory/agents/kuramoto.py
observatory/debug/debug_01_bus.py
observatory/debug/debug_02_single_agent.py
observatory/experiments/__init__.py
observatory/experiments/run_fireflies.py
observatory/monitors/__init__.py
observatory/monitors/convergence.py
observatory/requirements.txt
~~~~~

#### Acts 2: 提交变更

创建一个详尽的提交信息，总结这次关键的架构验证和修复。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(agent): Implement Firefly Agent (Kuramoto Model) and Observatory Tools

This monumental commit integrates the Firefly Agent, Monitor, and the necessary infrastructure (Observatory) to run self-organizing, long-running agent simulations.

Critical architecture fixes discovered during this process:

1.  fix(runtime/engine): Prevent TCO starvation of the event loop.
    Introduced `await asyncio.sleep(0)` inside the Engine's Tail Call Optimization loop. This prevents the engine from blocking the event loop during recursive calls, ensuring external tasks (like `asyncio.wait_for` and I/O handlers) can run, fixing the premature exit bug.

2.  fix(runtime/resource): Correctly pass Connector in deep recursion.
    Bypassed the implicit resource injection (`cs.inject`) for `_internal_connector` in the Agent logic by manually passing the Connector object as an explicit argument. This ensures reliable resource access in multi-engine, recursive contexts.

3.  fix(graph/build): Explicit dependency for side effects.
    Fixed an issue where the `GraphBuilder` ignored dependency edges defined via Python default arguments (e.g., `_flash_dependency=flash_action`), pruning critical side-effect tasks. Dependencies must now be explicitly passed as call arguments to guarantee inclusion in the graph.

4.  feat(observatory): Adds Firefly Agent and Convergence Monitor.
    -   Implements `firefly_agent` using `safe_recv` (timeout as data) and recursive workflow.
    -   Adds `ConvergenceMonitor` to calculate the Kuramoto Order Parameter (R) in real-time.
    -   Fixes a physical bug where Agent phase calculation ignored elapsed wait time.
~~~~~

### 下一步建议
我们已经完成了对 Cascade 架构的极限测试。现在，我们应该将这次宝贵的经验应用到主线任务上。

我建议启动下一个阶段：**阶段五：躯体与记忆 (Soma & Memory)**，从实现全局状态总线开始。

- **新任务**: **里程碑 5.1: 实现 `RedisStateBackend`**。
- **目的**: 为 Cascade 工作流提供持久化、可恢复性，并实现跨进程的协作能力。
- **起始文件**: 我们需要从 `cascade-runtime` 包中定义新的 Redis 后端。

如果你同意，我将创建新的计划来实施 `RedisStateBackend`。
