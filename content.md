好的，所有测试都已通过。我们已经成功完成了这次关键的架构重构，现在是时候将其作为一个逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划。

## [COMMIT] refactor(core, graph): Rename Node.id to structural_id and extract HashingService

### 用户需求
解决 `GraphBuilder` 的职责耦合（SoC Violation）问题，并通过将 `Node.id` 重命名为 `Node.structural_id` 来澄清其模糊的语义。

### 评论
这是一次根本性的架构改进。通过提取 `HashingService` 并将 `id` 重命名为 `structural_id`，我们为节点身份建立了一个清晰、正式的定义。这解决了实例唯一性（正确性）和模板可复用性（性能）之间的战略性矛盾，为未来的 JIT 缓存等高级优化铺平了道路。

### 目标
创建一个单一、原子的 Git 提交，封装所有与 `structural_id` 重构和 `HashingService` 创建相关的变更。

### 基本原理
重构已完成，所有测试均已通过，这标志着项目达到了一个稳定的、逻辑上完整的检查点。立即提交可以将这一基础性架构变更与后续工作（如修复其他架构缺陷）清晰地隔离开来，并形成有价值的历史记录。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/graph #comp/tests #concept/graph #scope/api #scope/core #ai/refine #task/domain/core #task/object/graph-builder #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有相关变更

我们将所有被修改和新建的文件添加到 Git 的暂存区。

~~~~~act
git_add
packages/cascade-graph/src/cascade/graph/hashing.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-engine/src/cascade/runtime/flow.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
packages/cascade-engine/src/cascade/adapters/solvers/native.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-sdk/src/cascade/tools/visualize.py
packages/cascade-sdk/src/cascade/tools/lisp.py
packages/cascade-sdk/src/cascade/tools/preview.py
tests/engine/graph/test_hashing.py
tests/sdk/tools/test_visualize.py
tests/engine/adapters/executors/test_local.py
tests/engine/adapters/solvers/test_csp.py
tests/engine/graph/test_serialize.py
tests/engine/integration/test_engine_vm_integration.py
tests/engine/runtime/test_flow_manager.py
tests/engine/runtime/test_router_pruning.py
tests/spec/spec/test_routing.py
~~~~~

#### Acts 2: 提交变更

现在，我们创建一个内容详尽的提交，记录本次重构的动机和实现。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core, graph): Rename Node.id to structural_id and extract HashingService

This commit addresses a core architectural flaw and a strategic contradiction in the definition of node identity.

**Problem:**
1.  **SoC Violation:** `GraphBuilder` was a "God Object" responsible for graph traversal, hashing, and static analysis.
2.  **Semantic Ambiguity:** `Node.id` was a confusing term, trying to represent an instance's unique identity while `Node.template_id` represented its structural blueprint. The hashing logic for constraints was inverted, compromising both correctness and performance goals.

**Solution:**
1.  **Extract `HashingService`:** All Merkle hash computation logic is now encapsulated in `cascade.graph.hashing.HashingService`. This isolates the concern of "identity" from "construction". `GraphBuilder` is now a pure structure mapper.
2.  **Rename `Node.id` to `Node.structural_id`:** This makes the purpose of the ID explicit. It is the hash of the node's complete structure, including literal values, making it the perfect key for instance-specific caching.
3.  **Formalize Hashing Rules:** The `HashingService` implements the new, correct hashing semantics:
    - `structural_id` includes all information (keys and values) to guarantee instance uniqueness.
    - `template_id` normalizes literals to enable performance optimizations like JIT plan caching.

This change resolves the strategic conflict, clarifies the core data model, and provides a stable foundation for future performance enhancements outlined in the architecture roadmap.
~~~~~
