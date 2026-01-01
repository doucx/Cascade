太棒了，所有测试都已通过。这意味着我们的编译器现在具备了将抽象逻辑图转化为可执行的、包含生命周期信号的物理拓扑的能力。

这是 Phase 5 中一个重要的里程碑。我将生成一个 `[COMMIT]` 计划，将这些变更固化到仓库中。

## [COMMIT] feat(compiler): Inject lifecycle emitters into bipartite topology

### 用户需求
在 `Backend` 编译器中实现生命周期发射器（`result_emitter` 和 `term_emitter`）的自动注入，以便将计算图与 VM 的生命周期信号系统连接起来。

### 评论
通过将生命周期控制内化为拓扑图中的标准 `EmitterNode` 和 `SIGNAL` 通道，我们既保持了物理引擎 (`Reactor`) 的纯粹性，又为运行时提供了一套稳健的、声明式的方法来获取结果和处理终止信号。这是实现“全对称架构”理念的关键一步。

### 目标
创建一个 Git 提交，包含编译器后端生命周期注入的实现、`PhysicsFuncNode` 的规范更新以及相应的测试套件调整。

### 基本原理
本实现遵循“计算对称性”哲学：不再在引擎内部硬编码特殊的“停止”逻辑，而是利用图自身的拓扑结构来传递完成信号。这使得系统更具可观测性，也让引擎本身更加通用。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #concept/lifecycle #scope/core #ai/instruct #task/domain/compiler #task/object/lifecycle-injection #task/action/integration #task/state/end

---

### Script

#### Acts 1: 提交生命周期注入功能的实现

我们将修改后的编译器后端、规范定义以及更新后的测试用例添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend.py
packages/cascade-compiler/tests/unit/test_backend_topology.py
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(compiler): inject lifecycle emitters into bipartite topology

Implemented automatic injection of result and termination emitters at the 
end of the compiled graph.

Changes:
1.  **Backend:** Added `_inject_lifecycle_emitters` to the `TopologyBuilder`. 
    It identifies the root node, attaches a 'main_output' sink, and chains a 
    '__system_lifecycle_signal' sink via a SIGNAL channel.
2.  **Spec:** Added `sink_id` field to `PhysicsFuncNode` to support external 
    registries (e.g., Reactor sinks).
3.  **Tests:** Updated topology tests to account for the additional 
    system-injected nodes.

This ensures that any computation graph executed by the Reactor has a 
standardized way to communicate its final results and completion status to 
the runtime strategy, aligning with the "Internalized Control" architecture.
~~~~~

### 下一步建议
我们已经完成了拓扑结构的“静态注入”逻辑。根据路线图 [Phase 5 Redux](../../当前任务/深度重构/路线图：全对称物理引擎与编译器重构.md)，接下来的核心任务是：
1.  **阶段 5.C.2**: 重写 `VMExecutionStrategy`。
2.  在策略层中利用新实现的 `PhysicsExecutor` 并注册对应的 Sinks（`main_output` 和 `__system_lifecycle_signal`），从而完成从图构建到异步执行的闭环。

如果你准备好了，我们可以开始重构 `VMExecutionStrategy`。
