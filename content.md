好的，我们已经成功完成了 Phase 1 和 Phase 2，并且修复了迁移带来的所有导入问题，测试已全面通过。现在是将这些结构性变更作为一个完整逻辑单元提交的时候了。

## [COMMIT] feat(runtime): Extract legacy graph executor into 'cascade-execution-graph'

### 用户需求
按照重构路线图，将遗留的图执行逻辑从 `cascade-runtime` 剥离，建立独立的 `cascade-execution-graph` 包，并恢复 SDK 的公共 API 访问。

### 评论
这次重构是实现“Y 型架构”的关键一步。通过将遗留实现物理隔离，我们不仅精简了 `cascade-runtime` 的依赖（例如移除了对 `python-constraint` 的强制依赖），还为未来引入基于 VM 的现代执行路径扫清了障碍。这是一次高保真的架构演进。

### 目标
1.  提交新包 `cascade-execution-graph` 的所有脚手架文件。
2.  提交从 `cascade-runtime` 迁移至新包的所有源代码文件（由 Stitcher 迁移工具执行）。
3.  提交为了适配新包结构而修改的所有测试文件和 SDK 导出配置。
4.  更新根目录工作区配置。

### 基本原理
我们通过物理分离实现了“关注点分离” (SoC)。`cascade-runtime` 现在更接近于一个纯粹的宿主环境，而具体的执行策略则变成了可插拔的插件。虽然目前 `Engine` 仍然存在逻辑上的耦合（将在 Phase 3 解决），但物理层面的拆分已经完成。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/build #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/decoupling #task/action/migration #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交结构性变更

我们将新包、迁移后的代码、修复后的测试以及工作区配置添加到暂存区并执行提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Extract legacy graph executor into 'cascade-execution-graph'

This commit executes a major architectural split as part of the "Runtime Decoupling" roadmap. The legacy graph-based execution logic has been moved from the core 'cascade-runtime' package into a new standalone package 'cascade-execution-graph'.

Key changes:
- Created 'packages/cascade-execution-graph' with its own build configuration and dependencies (including python-constraint).
- Migrated 'graph' models, 'solvers', and 'legacy' logic (FlowManager, NodeProcessor, Resolvers) using Stitcher's semantic refactoring tool.
- Updated root 'pyproject.toml' to include the new package in the workspace.
- Fixed all test imports and updated 'cascade-sdk' import mapping to maintain public API compatibility.

This separation prepares 'cascade-runtime' to become a clean host environment for the upcoming VM-based execution path while keeping the legacy implementation available as an optional plugin.
~~~~~

### 下一步建议

我们已经完成了宏观任务的第二阶段。

接下来的任务是 **Phase 3: 引擎解耦 (Engine Decoupling)**。
我们需要修改 `cascade-runtime` 中的 `Engine` 类，使其不再硬编码导入 `GraphExecutionStrategy`。相反，它应该通过依赖注入接收策略，并能根据环境动态加载。这将使 `cascade-runtime` 真正实现“宿主与实现”的逻辑分离。

如果你准备好了，我们将开启下一个任务阶段。
