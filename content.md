## [WIP] fix(engine): Correct GraphBuilder hash logic to fix parallel execution and test regressions

### 错误分析
当前的 `test_wait_is_non_blocking` 和 `test_wait_accepts_lazy_result` 失败是因为 `GraphBuilder` 构建的图存在逻辑缺陷，导致原本应该并行的任务被串行化执行。

1.  **并行任务串行化**: 当 `GraphBuilder` 采用自底向上（Merkle）的哈希构建时，如果两个子节点（`wait` 和 `immediate`）的哈希计算方式存在隐患（例如对 `kwargs` 的排序不稳定），可能会导致生成的 `wrapper` 节点在哈希中隐含了某种顺序依赖，或者 Solver 在处理哈希顺序时产生了非确定性。更重要的是，如果哈希中包含了 UUID，那么每次构建的节点 ID 都是全新的，这让任何基于 ID 的去重机制失效。
2.  **基准测试性能下降**: 由于必须引入 UUID 来保证实例唯一性（修复 `sequence` 问题），导致简单的任务模板缓存完全失效。这是目前必须接受的代价，直到下一阶段实现“模板哈希”。

本次修复的首要任务是**恢复正确性**：确保并行任务真正并行，确保 `sequence` 真正按顺序执行。

### 用户需求
1.  修复 `test_wait_is_non_blocking` 和 `test_wait_accepts_lazy_result` 两个时间相关的测试失败。
2.  确保所有其他测试（包括 `sequence`）继续通过。

### 评论
我们现在的策略是“正确性优先”。这意味着我们将专注于让图的结构完全正确，哪怕这意味着当前的性能暂时不是最优的。只有在所有测试都通过的基础上，我们才能安全地在下一阶段实施激进的性能优化。

### 目标
1.  修改 `GraphBuilder` 的哈希逻辑，确保它是稳定且正确的。
2.  确保 `test_wait_is_non_blocking` 通过（并行任务不应相互阻塞）。

### 基本原理
目前的失败表现为 `Execution took 0.20s` (expected ~0.1s)，这强列暗示 `wait(0.1)` 和另一个瞬时任务被串行执行了。这通常意味着图结构中存在意外的依赖边，或者 Solver 在生成 Plan 时过于保守。我们将检查 `GraphBuilder` 是否错误地在并行参数之间引入了依赖，并确保哈希计算的稳定性。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/engine #comp/graph #concept/hashing
#ai/instruct
#task/domain/core #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 GraphBuilder 哈希逻辑与并行处理

我们将微调 `build.py` 中的哈希计算逻辑，确保它是绝对确定的（使用排序），并且不会在并行参数之间引入任何顺序暗示。同时，我们将显式检查 `test_wait` 失败的原因是否与某些隐式边的生成有关。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # Combine shell, UUID, and children IDs
        # We use a tuple to hash, which is very efficient in Python
        child_hashes = tuple((c.id, path, etype) for c, path, etype, _ in child_edges)
        
        # The node_hash uniquely identifies this specific instance in the graph
        node_hash_int = hash((shell_hash, result._uuid, child_hashes))
        # Convert to string for ID compatibility
        node_hash = f"{node_hash_int:x}"
~~~~~
~~~~~python
        # Combine shell, UUID, and children IDs
        # We use a tuple to hash, which is very efficient in Python
        
        # CRITICAL: Sort child hashes to ensure deterministic Node ID regardless of 
        # dictionary iteration order (e.g. kwargs). This is vital for correct graph structure.
        # However, for 'args' (positional), order matters.
        # 'child_edges' is currently built by iterating args then kwargs.
        # Since 'args' order is significant but 'kwargs' key order is sorted by the visitor,
        # relying on list order is generally safe IF the visitor guarantees sorted kwargs.
        
        # Let's verify the visitor logic:
        # for i, val in enumerate(result.args): ... (Ordered)
        # for k, val in result.kwargs.items(): ... (Dict insertion order in Py3.7+, but let's be safe)
        
        # To be absolutely robust, we should trust the 'path' in child_edges to carry the order info.
        # So sorting child_hashes by path is safe and correct.
        
        # Sort by path to ensure deterministic hashing
        child_hashes = tuple(sorted(
            ((c.id, path, etype) for c, path, etype, _ in child_edges),
            key=lambda x: x[1] # Sort by arg path
        ))
        
        # The node_hash uniquely identifies this specific instance in the graph
        node_hash_int = hash((shell_hash, result._uuid, child_hashes))
        # Convert to string for ID compatibility
        node_hash = f"{node_hash_int:x}"
~~~~~

#### Acts 2: 修正 GraphBuilder 访问者顺序

为了配合上述哈希逻辑的稳定性，我们需要确保 `_visit_lazy_result` 中访问子节点的顺序是确定性的（特别是 `kwargs`）。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        for i, val in enumerate(result.args):
            visit_child(val, str(i))
        for k, val in result.kwargs.items():
            visit_child(val, k)
        
        if result._condition:
~~~~~
~~~~~python
        for i, val in enumerate(result.args):
            visit_child(val, str(i))
        
        # Sort kwargs keys to ensure deterministic traversal order
        for k in sorted(result.kwargs.keys()):
            val = result.kwargs[k]
            visit_child(val, k)
        
        if result._condition:
~~~~~

### 下一步建议
1.  运行 `pytest tests/sdk/providers/test_time_provider.py` 验证 `test_wait` 修复情况。
2.  运行完整测试套件 `pytest` 确保没有其他回归。
3.  如果测试全部通过，我们将进入“通用缓存”的实施阶段。
