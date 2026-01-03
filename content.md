好的，阶段 1 的物理层完备化（扩展物理定义与异步 Reactor 重构）已经通过了所有回归测试，证明了异步非阻塞模型的稳定性。

我将生成一个 `[COMMIT]` 计划，将这些核心变更提交到 Git 仓库。

## [COMMIT] refactor(vm): 实现异步非阻塞 Reactor 并扩展物理端口定义

### 用户需求
完成 Phase 5 阶段 1 的物理层完备化，并将变更提交至 Git 仓库。

### 评论
这次重构是 Cascade 3.0 的基石。通过将 `Reactor` 从同步步进升级为异步非阻塞调度，我们真正实现了“物理场”的并发演化能力。`active_task_count` 的引入为上层策略提供了精确的系统静止检测手段，而端口名称的标准化则消除了系统中的硬编码魔法字符串。

### 目标
1.  提交 `cascade-spec` 中标准端口定义（`PortName`）的变更。
2.  提交 `cascade-vm` 中 `VolatileMemory` 事件驱动机制和 `Reactor` 异步重构的变更。
3.  提交所有修复后的单元测试和集成测试。

### 基本原理
按照 TDD 流程和重构路线图，阶段 1 的代码修改已通过所有测试验证（包括 `cascade-vm` 的物理逻辑测试和 `cascade-compiler` 的集成阻塞测试），达到了 `GREEN` 状态。作为一个逻辑完整且稳定的工作单元，现在可以进行原子提交。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/vm #comp/tests #scope/core #ai/instruct #task/domain/core #task/object/physics-layer #task/action/completion #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交物理层完备化变更

我们将所有涉及物理定义扩展、VM 异步重构以及配套测试修复的文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ports.py
packages/cascade-vm/src/cascade/vm/memory.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-vm/tests/integration/test_branching.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): implement async non-blocking reactor and extend physical specs

This commit completes Phase 1 of the Cascade 3.0 Integration Strategy.

Key Changes:
1.  **Spec Extension**: Introduced 'PortName' constants in cascade-spec to standardize names for resources (REQ/REL/GNT), worker I/O, trace, and observability ports.
2.  **Event-Driven Memory**: Upgraded VolatileMemory with an 'asyncio.Event' based mutation notification system, enabling efficient 'wait_for_mutation' patterns.
3.  **Async Reactor**: Refactored the Reactor to be non-blocking. The 'step()' method now schedules tasks using 'asyncio.create_task' and returns immediately.
4.  **Sovereignty Support**: Added 'active_task_count' and 'sinks' (port-level callbacks) to the Reactor, allowing external observers to monitor lifecycle and extract results without violating graph integrity.
5.  **Test Harmonization**: Updated all unit and integration tests to handle the new asynchronous behavior using deterministic 'wait_for_idle' or 'wait_for_mutation' patterns.

This refactoring shifts Cascade from a 'step-and-wait' model to a continuous 'physics field' evolution model, laying the foundation for high-performance resource brokering and reactive control flow.
~~~~~

### 下一步建议
阶段 1 已完美结束。接下来我们将进入 **阶段 2: 编译器的智能化 (Compiler Intelligence)**。

我建议下一步从 **任务 2.1: Frontend 增强** 开始，实现以下功能：
1.  **参数探测 (ParamProbe)**：当 `IRGenerator` 遇到字面量参数时，自动将其包装为探测节点。
2.  **资源自动识别**：自动解析 `LazyResult` 的约束并将其映射到 IR 层。

准备好后请告知，我将为你生成详细的实施计划。
