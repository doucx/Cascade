好的，我们已经成功完成了 Cascade 架构演进中极具挑战性的第一步：“心脏移植”手术——结构与数据的彻底分离。测试套件已完全通过，系统现在运行在全新的 `(GraphTemplate, DataTuple)` 模型之上。

现在，我将生成 `[COMMIT]` 计划，将这些重大的底层变更封装为一个原子的、生产级的提交。

## [COMMIT] refactor(core): 实现“结构数据分离”模型 (The Great Split)

### 用户需求
按照 [Cascade 架构重构 - 结构数据分离 (v3.0)] 路线图，完成第一阶段所有任务：实现节点纯化、数据外置，并重构核心构建器与执行器以支持“模板-实例分离”模式。

### 评论
这是 Cascade 迈向高性能计算引擎的关键里程碑。通过将计算图（拓扑骨架）与运行时数据（血肉）解耦，我们不仅使图对象变小且不可变，更重要的是，我们为接下来的 Hashlife 缓存、零开销递归优化以及跨进程图分发铺平了道路。虽然这是一个破坏性重构，但其带来的长期架构收益是巨大的。

### 目标
1.  提交 `cascade-spec` 中的数据绑定原语 (`SlotRef`, `Constant`)。
2.  提交 `cascade-graph` 中重构后的 `Node` 模型和 `GraphBuilder`。
3.  提交 `cascade-engine` 中适配新模型的 `ArgumentResolver`、`NodeProcessor` 和执行策略。
4.  提交受影响的 SDK 工具（`preview`, `visualize`）及全量测试套件的修复。

### 基本原理
我们引入了间接寻址机制：节点不再直接持有字面量参数，而是持有对一个外部扁平元组（DataTuple）的索引引用（SlotRef）。这种设计允许相同的代码逻辑共享同一个图模板。执行引擎在调度时根据模板确定顺序，在执行前的一刻才根据 DataTuple 进行数据“水合 (Hydration)”。

### 标签
#intent/refine #flow/ready #priority/critical #comp/core #comp/engine #comp/graph #concept/data-model #scope/core #ai/instruct #task/domain/core #task/object/data-model #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交变更到 Git

我们将所有核心模块、SDK 工具以及修复后的测试用例添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/binding.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-engine/src/cascade/runtime/resource_container.py
packages/cascade-sdk/src/cascade/tools/events.py
packages/cascade-sdk/src/cascade/tools/preview.py
packages/cascade-sdk/src/cascade/tools/visualize.py
tests/engine/runtime/test_engine_core.py
tests/engine/adapters/solvers/test_csp.py
tests/engine/adapters/solvers/test_native.py
tests/engine/graph/test_serialize.py
tests/engine/graph/test_build.py
tests/engine/graph/test_build_tco.py
tests/spec/spec/test_constraint.py
tests/sdk/tools/test_preview.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Implement 'The Great Split' - Structural-Data Separation

This commit implements the "Template-Instance Separation" pattern, a foundational 
step for the Hashlife-style structural caching and zero-overhead TCO.

Core Changes:
1. **Data Model (spec & graph):**
   - Introduced `SlotRef` and `Constant` in `cascade.spec.binding`.
   - Purified `Node` model by replacing `literal_inputs` (data) with `input_bindings` (references).
   - `Graph` is now a `GraphTemplate`, decoupled from runtime literal values.

2. **GraphBuilder (graph):**
   - Rewrote `GraphBuilder.build()` to return a `(Graph, DataTuple)` pair.
   - Implemented literal data extraction logic that flattens arguments into an external buffer during graph construction.

3. **Runtime Engine (engine):**
   - Re-engineered `ArgumentResolver` to perform "data hydration" by combining structural bindings with the `DataTuple`.
   - Fixed a critical logical flaw in `Router` resolution within the new model.
   - Updated `NodeProcessor` and `ExecutionStrategy` to propagate the `DataTuple`.
   - Upgraded `ResourceContainer` to scan for `Inject` markers within both the static graph and the dynamic data tuple.

4. **Tooling & Tests (sdk & tests):**
   - Adapted SDK developer tools (`dry_run`, `visualize`) and events to use `input_bindings`.
   - Fixed over 130 failing tests across the suite, ensuring 100% compliance with the new architecture.

This refactor lays the groundwork for O(1) recursion performance and ultra-fast 
cached graph execution in upcoming phases.
~~~~~

### 下一步建议
我们已经完成了地基的搭建。根据路线图，接下来的重点是：

1.  **[COMMIT 2] 重建核心 - 实现规范化构建器 (Node Interning)**：既然结构和数据已经分离，我们现在可以实现基于哈希的节点池化。如果两个子图结构完全相同（即使数据不同），它们应该在内存中共享同一个 `Node` 对象。
2.  **[COMMIT 3] 通用缓存实现 - 启用 Hashlife 缓存**：基于结构哈希缓存 `GraphTemplate` 和对应的 `ExecutionPlan`，实现真正的“一次构建，多次运行”。

建议我们首先开始 **2.1 全局/会话级节点注册表 (Node Interning)** 的开发。
