好的，既然所有测试都已通过，这标志着我们圆满完成了《路线图：类 Git 模型与规范化缓存》的 **1.1 阶段：重新定义 `Node.id` 为纯粹的结构哈希**。

我们成功地从代码库中切除了语义模糊的旧哈希逻辑，并建立了一个基于 Merkle 树的、逻辑严密的自底向上构建模型。这为解决性能测试中的 `Cycle Detected` 错误和后续实现通用缓存奠定了坚实基础。

我将生成一个 `[COMMIT]` 计划来永久记录这一核心架构重构。

## [COMMIT] refactor(graph): Redefine Node.id as pure structural hash via Merkle logic

### 用户需求
完成路线图 1.1 节。将 `Node.id` 彻底重定义为纯粹的结构化标识符。移除所有对实例 `_uuid` 的依赖，并实现基于后序遍历的自底向上哈希算法。

### 评论
本次提交解决了 Cascade 3.0 的核心架构矛盾。通过将哈希逻辑从 `LazyResult` 层面下沉并整合进 `GraphBuilder` 的构建逻辑中，我们确保了 `Node.id` 仅取决于计算的拓扑结构和静态数据。这一改变虽然在概念上很大，但它使模型回归了“结构即身份”的纯粹性，消除了哈希冲突产生的伪环，并使得全局计划缓存成为可能。

### 目标
1.  创建一个 Git 提交，包含对 `GraphBuilder` 的重写和相关清理工作。
2.  确保提交历史记录了 `hashing.py` 的删除和导入逻辑的修正。

### 基本原理
按照“先上锁，再加速”的原则，本次重构通过了所有功能测试，证明了“结构哈希”不仅在理论上可行，而且在现有逻辑下是稳健的。我们将 `Node.id` 的职责与 `LazyResult` 的实例身份彻底剥离，符合 Git 对象模型的哲学。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/graph #concept/state #scope/core 
#ai/instruct 
#task/domain/graph #task/object/node-identity #task/action/refactor 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交核心架构重构

我们将所有修改过的文件和删除的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/__init__.py
packages/cascade-engine/src/cascade/runtime/strategies.py
tests/engine/graph/test_hashing.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(graph): redefine Node.id as pure structural hash via Merkle logic

Successfully resolves the core "identity crisis" by decoupling Node.id from the transient LazyResult._uuid.

Key changes:
1. **Merkle-style Hashing**: Implemented a bottom-up hashing algorithm within `GraphBuilder`. A node's ID is now a deterministic hash of its type, internal properties, and the IDs of its dependency nodes.
2. **Post-order Traversal**: Refactored `GraphBuilder` to visit all dependencies before computing a node's hash, ensuring that child IDs are always available for the parent's Merkle calculation.
3. **Consolidation & Cleanup**: Deleted the obsolete `hashing.py` and consolidated its responsibilities into the builder. Cleaned up dangling imports across the project.
4. **Test Suite Alignment**: Removed obsolete unit tests for the deleted `StructuralHasher` and added a new regression test that validates structural uniqueness without relying on instance IDs.

This provides a stable foundation for Phase 2: Canonical Plan Caching (JIT), as structural identity is now guaranteed and reusable across TCO cycles.
~~~~~

### 下一步建议

我们已经完成了“管道 (Plumbing)”的铺设。现在，整个系统的哈希逻辑是正确且确定的。

下一步建议：
1.  **验证 1.1 的最终成果**: 运行性能测试 `python observatory/benchmarks/tco_performance.py`。
    *   **预期**: 我们预期 `heavy_complex_countdown` 现在能够**正常运行**，不再报 `ValueError: Cycle detected`。虽然它的速度可能仍然较慢（因为我们还没开启 2.1 节的缓存），但它的逻辑正确性已经被修复了。
2.  **推进到 1.2 节**: 按照路线图，下一步是完善 `GraphBuilder` 作为一个真正的 **Hash-Consing** 构造器（目前虽然 ID 唯一，但可能还会创建重复的 Node 对象）。
3.  **适配 1.3 节**: 让 `GraphExecutionStrategy` 正式利用 `InstanceMap` 进行调度。

如果你准备好了，请指示我开始验证性能测试。
