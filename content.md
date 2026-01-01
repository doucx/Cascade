好的，我们已经完成了 `PhysicsExecutor` 的实现、`TerminatorNode` 的废除以及测试的适配。现在我们将这些变更作为一个逻辑完备的单元提交。

## [COMMIT] feat(vm): Implement PhysicsExecutor and decouple lifecycle from Reactor

### 用户需求
完成路线图阶段 5.B，包括创建原生物理执行器、废除硬编码的终止节点，并验证基于外部控制的生命周期模型。

### 评论
这是 Cascade 架构演进中的一个里程碑。通过这一系列修改，我们成功地将 `Reactor` 从一个受限的任务执行器转变为一个通用的、纯粹的物理引擎。`PhysicsExecutor` 的引入实现了执行逻辑的解耦，而 `TerminatorNode` 的废除则实现了生命周期策略的控制反转。这为后续 5.C 阶段的编译器集成和 `VMExecutionStrategy` 的重构铺平了道路，使系统更具扩展性和鲁棒性。

### 目标
1.  提交 `PhysicsExecutor` 及其测试用例。
2.  提交对 `TerminatorNode` 的移除（包括 Spec 和 Reactor 逻辑）。
3.  提交适配后的 `EmitterNode` 生命周期测试。

### 基本原理
我们遵循“高保真、低耦合”的设计原则。将执行器和生命周期控制从引擎核心中剥离，不仅简化了核心逻辑，还使得引擎可以支持更多样化的执行场景（如分布式执行、无限循环流等）。在 Git 提交中，这些相关的修改应作为一个整体被记录，以保持项目历史的逻辑完整性。

### 标签
#intent/build #intent/refine #intent/tooling #flow/ready #priority/high 
#comp/engine #comp/spec #comp/tests #concept/executor #concept/state #scope/core 
#ai/instruct 
#task/domain/vm #task/object/physics-executor #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及物理模型简化、执行器实现以及测试适配的文件添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-spec/src/cascade/spec/topology.py
packages/cascade-vm/src/cascade/vm/__init__.py
packages/cascade-vm/src/cascade/vm/executors/__init__.py
packages/cascade-vm/src/cascade/vm/executors/physics.py
packages/cascade-vm/src/cascade/vm/reactor/core.py
packages/cascade-vm/tests/reactor/test_result_emission.py
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): Implement PhysicsExecutor and decouple lifecycle from Reactor

This commit completes Phase 5.B of the engine refactoring roadmap.

Key changes:
1.  **PhysicsExecutor:** Introduced a native executor for the physics-based VM. It bridges the Reactor and the symbol table, handling both sync and async function execution and error reporting.
2.  **Lifecycle Decoupling:** Abolished 'TerminatorNode' and 'PhysicsTerminatorNode' from the core specifications and Reactor logic. The Reactor no longer has internal knowledge of "termination".
3.  **Inversion of Control:** Lifecycle management is now an external strategy. The Reactor only emits results via EmitterNodes, and external controllers (like VMExecutionStrategy or tests) are responsible for stopping the reactor loop.
4.  **Test Adaptation:** Updated existing tests to reflect the new decoupled model, using explicit external control signals (asyncio.Future and reactor.stop()).

This transition moves Cascade towards a purer bipartite graph execution model, where control flow is strictly a byproduct of topology and token routing.
~~~~~

### 下一步建议
我们已经完成了底层物理执行器和生命周期模型的清理。接下来的核心任务是 **阶段 5.C：编译器与策略层的最终集成**。

具体步骤如下：
1.  **阶段 5.C.1**: 修改 `cascade-compiler`。更新 `Backend` 以支持生成符合新规范的 `EmitterNode` 拓扑。
2.  **阶段 5.C.2**: 重写 `VMExecutionStrategy`。将其从旧的 `VirtualMachine` 切换到新的 `Reactor` + `PhysicsExecutor` 组合。

我建议立即开始 **阶段 5.C.1** 的编译器适配工作。如果你准备好了，请告知。
