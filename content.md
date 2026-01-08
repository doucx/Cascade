好的，我们已经成功完成了 `PhysicsKernel` 的集成，并修复了受影响的测试用例。现在我将生成一个 `[COMMIT]` 计划来提交这些更改。

## [COMMIT] refactor(vm): integrate PhysicsKernel into Reactor and update tests

### 用户需求
正式提交对 `Reactor` 的重构，将其执行逻辑委托给 `PhysicsKernel`，并同步更新所有受影响的测试用例，以保持系统架构的严密性和测试的有效性。

### 评论
这次重构虽然涉及多个文件，但其核心逻辑非常清晰：通过引入 `PhysicsKernel` 作为执行层代理，解耦了 `Reactor` 的拓扑管理与具体 IC 函数的调用逻辑。这不仅符合 HFEA 原则，也为未来在物理层引入更复杂的执行策略（如资源预分配、性能审计等）打下了基础。

### 目标
1.  提交 `PhysicsKernel` 类型签名的修正。
2.  提交 `Reactor` 对 `PhysicsKernel` 的集成。
3.  提交 `EventDrivenRunner` 中对组件组装逻辑的更新。
4.  提交所有修复后的集成测试和单元测试。

### 基本原理
通过 `git add` 将所有相关修改加入暂存区，并创建一个语义明确的 `git commit`。这次变更是一个逻辑完整的工作单元，它恢复了系统的“物理平衡”，使各组件职责归位。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/physics-kernel #task/action/integration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构重构与测试修复

我们将所有修改过的核心代码和测试文件添加到 Git，并创建一个详细的提交。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/kernel/core.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-compiler/tests/integration/test_branching.py
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
packages/cascade-vm/tests/integration/test_machine_integration.py
packages/cascade-vm/tests/integration/test_observability_congestion.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/integration/test_time_services.py
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): integrate PhysicsKernel into Reactor

This commit formalizes the separation between topological mechanics and semantic execution by integrating the `PhysicsKernel` into the `Reactor`.

Key Changes:
- Refactored `Reactor` to delegate IC execution to a `PhysicsKernel` instance instead of directly managing `function_map` and `ResourceRegistry`.
- Corrected `PhysicsKernel` signature to use `Token` instead of `Ref` for its inputs/outputs, aligning with the actual behavior of physical layer ICs.
- Updated `EventDrivenRunner` harness to assemble the `PhysicsKernel` during setup.
- Updated all unit and integration tests to comply with the new `Reactor` constructor signature.

This architectural shift ensures `Reactor` remains a pure bipartite graph engine, while `PhysicsKernel` handles the specifics of IC invocation and resource injection, facilitating future extensibility and potential performance optimizations (e.g., Rust-based reactor core).
~~~~~

### 下一步建议
- **回归测试**: 在不同环境下运行完整的测试套件，确保没有细微的竞态条件。
- **性能评估**: 观察 `PhysicsKernel` 这层轻量级封装对每秒激发次数 (FPS) 的影响，虽然理论上应该是微秒级的。
- **文档更新**: 如果有开发者文档描述了 Reactor 的初始化，请务必更新以反映新的 `Kernel` 依赖。
