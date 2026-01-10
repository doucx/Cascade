好的，现在我们已经完成了 `Engine` 的解耦以及依赖的清理，系统的架构边界已经变得清晰。是时候将这些重大的架构改进作为一个完整的逻辑单元提交到版本库了。

这将标志着重构路线图中 Phase 1 到 Phase 4 的正式完结。

## [COMMIT] refactor(runtime): 剥离遗留图执行器并解耦 Engine

### 用户需求
完成对 `cascade-runtime` 的架构重塑，正式确立“宿主-策略”分离的模式，并提交相关变更。

### 评论
这次重构是 Cascade 架构演进中的一个里程碑。我们不仅在代码物理位置上完成了迁移（建立了 `cascade-execution-graph` 包），更在逻辑上彻底切断了核心引擎对特定实现的依赖。这种“瘦身”让 `cascade-runtime` 变成了一个高度可扩展、低开销的现代化宿主环境。

### 目标
创建一个 Git 提交，包含以下变更：
1.  `cascade-runtime` 中的 `Engine` 解耦逻辑。
2.  `cascade-runtime` 的依赖清理。
3.  新创建的 `cascade-execution-graph` 包及其所有迁移的代码（假设这些文件已在工作区准备就绪）。

### 基本原理
按照“高保真工程公理 (HFEA)”，我们将具有本体论差异的组件（宿主环境与特定策略实现）进行了物理隔离。通过 `[COMMIT]` 计划，我们将这些分散的操作固化为一个确定性的架构快照。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/build #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/host-decoupling #task/action/commit #task/state/end

---

### Script

#### Acts 1: 提交架构重构变更

我们将把受影响的包文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/pyproject.toml
packages/cascade-execution-graph/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(runtime): Decouple Engine from legacy graph execution

Successfully implemented Phase 1 through 4 of the Runtime Refactoring Roadmap:

1. Package Separation: Established 'cascade-execution-graph' as a standalone package to host legacy Python-object-graph logic, resolvers, and solvers.
2. Engine Decoupling: Refactored 'cascade.runtime.host.Engine' to remove static compile-time dependencies on 'GraphExecutionStrategy' and 'NodeProcessor'.
3. Strategy Injection: The Engine now accepts an 'ExecutionStrategy' via its constructor. It implements dynamic loading of the legacy strategy for backward compatibility, preventing runtime crashes if the new package is present.
4. Dependency Cleanup: Removed 'python-constraint' from 'cascade-runtime', significantly reducing its dependency footprint.

This establishes a clean "Host-Plugin" architecture, paving the way for the high-performance VM-based execution strategy.
~~~~~

### 下一步建议
我们现在已经有了一个非常干净、解耦的宿主环境。根据路线图，我们的下一个宏观任务是：

**Phase 5: VM 策略引入 (VM Strategy Introduction)**

我建议我们开始实施这个阶段：
1.  **定义接口适配**: 在 `cascade-runtime` 中创建 `cascade/runtime/strategies/vm.py`。
2.  **实现 Hypervisor 逻辑**: 实现 `VMExecutionStrategy`，它将负责连接 `Engine` 与底层 `Cascade VM` 的数据面和控制面。

如果你准备好了，我们可以开始 Phase 5 的第一个步骤。
