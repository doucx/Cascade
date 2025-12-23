好的，现在所有测试已全部通过。

我们成功建立了一个基于“Git 对象模型”的、正确且自包含的计算图架构。尽管目前的 JIT 缓存受限于“数据即结构”的设计而表现出较为严格的命中条件，但它在逻辑上是无懈可击的，并为后续更高级的“模板-实例分离”优化奠定了坚实的基础。

我将生成一个 `[COMMIT]` 计划来固化这一里程碑。

## [COMMIT] feat(core): 实现自包含 Node 模型与 JIT 计划缓存

### 用户需求
完成 Cascade v3.2 路线图的第一阶段：实现规范化的图对象数据库，并启用初步的 JIT 计划缓存。

### 评论
这是一次深度的架构对齐。通过废弃复杂的 `DataTuple` 机制并将数据直接闭包在 `Node` 对象中，我们解决了缓存复用时的状态不一致问题。虽然这导致缓存键包含了参数值（使得变参递归无法命中缓存），但它保证了系统在高度动态环境下的绝对正确性。

### 目标
执行 Git 提交，包含所有架构重构、Bug 修复、接口清理以及新增的测试套件。

### 基本原理
将相关联的架构变更固化为一个原子提交。这不仅标志着路线图阶段任务的完成，也为未来的性能突击（例如实现真正的模板化缓存）提供了一个稳定、可回退的基线。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/engine #comp/graph #concept/state #scope/core #ai/instruct #task/domain/architecture #task/object/node-model #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有变更

我们将所有修改过的核心代码和测试文件添加到暂存区，并执行提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core)!: Implement self-contained Node and JIT cache (v3.2 milestone)

This major refactor stabilizes the Cascade v3.2 "Git Model" architecture, ensuring a consistent and deterministic relationship between a computation's structure and its runtime instance.

**Breaking Changes:**
- The `cascade.graph.build.build_graph` signature now returns `(Graph, InstanceMap)`.
- The `DataTuple` and `SlotRef` mechanisms have been completely removed.

**Core Architecture Refinement:**
- **Self-Contained Nodes:** Literal arguments are now stored directly in `Node.input_bindings`. This makes `Node` objects truly immutable value objects that can be safely interned and reused across different execution contexts.
- **Node Interning:** Introduced `NodeRegistry` to ensure that any two identical computation structures result in the same `Node` instance in memory.
- **JIT Caching:** Implemented `_plan_cache` in `GraphExecutionStrategy`. It caches `ExecutionPlan`s keyed by the `root_node_id` (Merkle Hash), skipping the solver for repeated structures.

**Bug Fixes:**
- **Registry Integration:** Fixed a bug where reused nodes were not correctly added to the current graph instance.
- **TCO State Isolation:** Implemented `InMemoryStateBackend.clear()` to ensure TCO iterations start with a fresh result map.
- **Resource Recovery:** Enhanced `ResourceContainer` with a robust `override` context manager and fixed state leakage in tests.

**Testing:**
- Comprehensive updates to the test suite to match the new API signatures.
- Added `test_tco_cache.py` to verify dependency resolution in cached TCO loops.
- Added `test_jit_cache_verification.py` to explicitly assert JIT cache hits via solver spying.
~~~~~

### 下一步建议
我们已经完成了“先上锁”的阶段。下一步的建议：
1.  **性能突破**: 探索“模板化哈希”机制。通过在计算 `Node.id` 时区分“结构参数”和“数据参数”，我们可以让 `heavy_complex_countdown(10)` 和 `heavy_complex_countdown(9)` 映射到同一个 `ExecutionPlan` 模板，从而真正释放 JIT 缓存的威力。
2.  **路线图更新**: 将 v3.2 路线图的第一阶段标记为已完成，并开始规划第二阶段的深度优化。
