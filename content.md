好的，我们已经完成了重构计划的前两步，并修复了所有连锁反应导致的测试和工具错误。现在的系统已经具备了“图即数据”的特征，并且执行层与图结构完全解耦。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交。

## [COMMIT] refactor(core): decouple graph topology from execution context

### 用户需求
完成“engine 与 graph 的预重构计划.md”中的步骤 1 和 步骤 2：解耦 `NodeProcessor` 与 `Graph`，以及解耦 `Node` 对象与 Python Callable。

### 评论
这是一次重大的架构演进，标志着 Cascade 从“对象图”模型转向了“纯数据图 + 运行时注入”模型。通过移除 `Node` 对 Python 函数的直接持有，并让 `NodeProcessor` 变成无状态的执行器，我们不仅实现了图的完全可序列化，还为未来的分布式执行、JIT 优化以及 v3.0 物理引擎的接入扫清了障碍。

### 目标
创建一个包含以下变更的 Git 提交：
1.  **逻辑上浮**: 将参数解析、约束解析和缓存准备逻辑从 `NodeProcessor` 移动到 `GraphExecutionStrategy`。
2.  **图的净化**: 移除 `Node`、`TaskNode` 和 `MapNode` 上的所有 Python 函数引用。
3.  **显示注入**: 引入 `ExecutableRegistry`，在运行时将任务实现显式注入到执行器中。
4.  **全量对齐**: 更新序列化 (JSON)、分析器 (IR)、SDK 工具 (Lisp/Visualize) 以及所有测试替身，以符合新的架构契约。

### 基本原理
我们严格执行了**“图的纯粹性”**公理：图只描述“是什么”和“怎么连”，而不包含“怎么做”的运行时细节。所有的执行能力现在都由执行环境 (`ExecutableRegistry`, `ResourceRegistry`) 提供，并在运行时通过 ID 链接。这种设计保证了系统在静态定义和动态执行之间有极度清晰的边界。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/engine #comp/graph #comp/sdk #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 提交重构变更

我们将所有受影响的文件添加到暂存区，并创建一个详尽的提交记录。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ir/models.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/runtime/resource_container.py
packages/cascade-engine/src/cascade/adapters/executors/local.py
packages/cascade-engine/tests/integration/test_engine_constraints.py
packages/cascade-application/src/cascade/app/__init__.py
packages/cascade-sdk/src/cascade/tools/lisp.py
packages/cascade-sdk/src/cascade/testing.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): decouple graph topology from execution context

This commit implements a major architectural shift by separating the static workflow definition (Graph) from its runtime implementation (Callables).

Key Changes:
1.  **Pure Data Graph**: Removed 'callable_obj', '_callable', and 'mapping_factory' from Node and its subclasses in 'cascade-graph'. Graph objects are now 100% serializable and environment-agnostic.
2.  **Decoupled NodeProcessor**: 'NodeProcessor.process' no longer accepts a 'Graph' object. It has been transformed into a pure execution unit that receives pre-resolved inputs, requirements, and the target executable.
3.  **ExecutableRegistry**: Introduced a runtime registry (Dict[str, Callable]) produced during graph building. This registry acts as the source of truth for task implementations during a specific run.
4.  **Strategy Orchestration**: 'GraphExecutionStrategy' now manages the lifecycle of the ExecutableRegistry and coordinates between Resolvers and the Processor.
5.  **Serialization & IR Enhancement**: Updated 'TaskDef' IR to include 'module' and 'qualname'. Redesigned 'serialize.py' to restore callables using these metadata fields instead of direct object references.
6.  **Tooling & Test Alignment**: Updated Lisp transpiler, visualization tools, and test spies (SpyExecutor) to handle the new triple-return from 'build_graph' and updated method signatures.

This refactoring fulfills the "Graph Purity" axiom and prepares the engine for the v3.0 physical triad model.
~~~~~

### 下一步建议
我们已经完成了前两个核心重构步骤。下一步是执行重构计划的**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。

在接下来的计划中，我将把 `NodeProcessor` 内部庞大的 `process` 逻辑拆解为 `_prepare_context` (Bleacher), `_execute_core` (Worker) 和 `_handle_outcome` (Stainer)。虽然这目前只是代码层面的重构，但它在逻辑上与 v3.0 的物理模型完全同构，将极大地降低后续“心脏移植”的风险。
