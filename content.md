好的，测试已通过，标志着我们成功完成了“阶段二：防线建设”。我们将现在创建一个 `[COMMIT]` 计划来记录这次重大改进。

## [COMMIT] feat(graph): 实现动态递归静态分析与警告

### 用户需求
提交静态分析功能，该功能用于检测 TCO 循环中的“动态递归”反模式，并在运行时向用户发出警告。

### 评论
本次提交显著提升了开发者体验 (DX)。通过在图构建时注入静态分析，我们能够主动警告用户潜在的性能瓶颈（CS-W001），指导他们编写出可被 Cascade 引擎高效优化的工作流。此外，本次提交还修复了因架构更改而产生的所有单元测试和集成测试缺陷，确保了整个图构建体系的健壮性。

### 目标
提交以下功能和修复：
1.  在 `Node` 模型中添加 `warns_dynamic_recursion` 标志。
2.  增强 `ast_analyzer`，实现 `CS-W001` (动态递归) 反模式检测。
3.  在 `GraphExecutionStrategy` 中集成警告发射逻辑，并添加状态管理以防止重复警告。
4.  添加相应的事件 (`StaticAnalysisWarning`) 和消息模板。

### 基本原理
**战略价值**: 这一功能在架构上将“静态图分析”提升为一级公民，并实现了性能优化路线图中的关键里程碑——“在让引擎变快之前，先让用户变聪明”。

**技术实现**: 静态分析结果被缓存在 `Task` 对象上，然后在 `GraphBuilder` 中映射到 `Node` 实例。`GraphExecutionStrategy` 在慢速路径中消耗此信息，通过事件总线发出警告，确保了核心逻辑与表现层的彻底解耦。同时，通过引入警告跟踪集合，解决了 TCO 循环中图重建导致的重复报告问题。

### 标签
#intent/feat #flow/ready #priority/high #comp/graph #comp/engine #comp/tests #scope/dx #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有修改的文件

将所有涉及 `cascade-graph`、`cascade-engine` 和 `cascade-common` 的文件添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/adapters/executors/__init__.py
packages/cascade-engine/src/cascade/adapters/solvers/__init__.py
packages/cascade-engine/src/cascade/runtime/events.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/runtime/subscribers.py
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
tests/engine/graph/test_ast_analyzer.py
tests/engine/runtime/test_static_analysis.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(graph, runtime): Implement static analysis for dynamic recursion anti-pattern (CS-W001)

This feature introduces a static linter to warn users about recursive TCO patterns that are structurally unstable, forcing the engine into the high-overhead "Heavy Path."

This completes the strategic "Phase Two: Static Analysis and Developer Guidance."

Key changes:
1.  **Graph Analysis (`ast_analyzer.py`)**: Enhanced the TCO visitor to detect when a recursive call contains other LazyResult dependencies in its arguments.
2.  **Node Model**: Added `warns_dynamic_recursion: bool` flag to `Node`.
3.  **Graph Builder**: The builder now uses the analysis result to set this flag on the `Node`.
4.  **Runtime Integration**: `GraphExecutionStrategy` checks this flag in the Slow Path, issues a `StaticAnalysisWarning` event, and tracks issued warnings by task name to prevent duplicates in TCO loops.
5.  **DX**: Added human-readable warning messages and corresponding unit/integration tests for end-to-end verification.
6.  **Fixes**: Corrected adapter package initialization and several `TypeError` issues caused by the `AnalysisResult` object transition.
~~~~~

### 下一步建议
我们现在可以开始执行性能优化路线图的最后一个关键阶段：

**阶段三：内核突破 —— 结构化 JIT 与动态修补 (Structural JIT)**。

**目标**: 利用我们在阶段一中构建的 `template_id` (L1 Hash) 来改造 TCO 策略。

具体步骤将是：
1.  修改 `GraphExecutionStrategy._are_args_simple` 方法，使其不再仅仅依赖于参数是否包含 `LazyResult`，而是直接依赖于 `target_node.template_id` 的存在和稳定性。
2.  当 TCO 循环命中 `template_id` 缓存时，我们不再调用昂贵的 `build_graph`，而是直接从缓存中取出 `ExecutionPlan` 模板，进行 JIT 动态修补，从而使 Heavy Path 任务获得与 Simple Path 相当的性能。

如果你同意，我将为此生成一个新计划。
