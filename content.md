## [WIP] fix(engine): Fix dependency cycles caused by hash collisions and metadata edges

### 错误分析
在运行 `tco_performance.py` 基准测试时，`heavy_complex_countdown` 任务触发了 `ValueError: Cycle detected in the dependency graph`。

经过深入排查，发现该错误由两个独立但叠加的因素导致：

1.  **元数据边干扰 (假环)**: `NativeSolver` 在进行拓扑排序时，错误地考虑了 `EdgeType.POTENTIAL` 等元数据边。这些边由静态分析生成，指向未来的递归调用，在当前执行上下文中并不构成依赖。如果简单的将其视为依赖，会形成逻辑上的环。
2.  **哈希冲突导致的节点错误复用 (真环)**: `ShallowHasher` 在计算 `LazyResult` 的哈希时，对于作为参数传入的嵌套 `LazyResult`，仅使用字符串 `"LAZY"` 作为占位符，而未包含其唯一标识（如 UUID）。这导致结构相似但层级不同的任务（如 `noop(d1)` 和 `noop(d2)`）生成了相同的哈希值。`GraphBuilder` 因此错误地将它们映射到同一个 `Node`，导致该节点通过 `DATA` 边指向自身，形成了真实的自环。

### 用户需求
修复 `heavy_complex_countdown` 基准测试中的循环报错，确保复杂递归任务能正常执行。

### 评论
这是一个涉及图构建核心逻辑的深层修复。
1.  通过在 `NativeSolver` 中引入**白名单**，我们明确了“执行依赖”的定义，将运行时调度与静态分析解耦。
2.  通过修正 `ShallowHasher`，我们消除了因哈希冲突导致的拓扑结构错误。虽然在 `ShallowHash` 中引入 UUID 会降低节点去重（Interning）的激进程度，但这对于保证执行图的正确性是绝对必要的——不同的 `LazyResult` 实例通常代表不同的计算步骤，不应被强制合并。

### 目标
1.  修改 `NativeSolver`，使其仅基于 `DATA`, `CONDITION` 等明确的执行依赖边进行排序。
2.  修改 `ShallowHasher`，在计算哈希时包含 `LazyResult` 参数的 UUID，防止错误的节点合并。
3.  验证 `tco_performance.py` 通过。

### 基本原理
*   **Solver 白名单**: 只有代表数据流向或控制流向的边（如 `DATA`, `SEQUENCE`）才应限制执行顺序。元数据边（如 `POTENTIAL`）是信息性的，不应影响调度。
*   **哈希唯一性**: `ShallowHasher` 用于在构建图中查找节点。如果两个 `LazyResult` 对象代表不同的计算步骤（即它们是不同的实例，且在依赖链的不同位置），它们必须映射到不同的图节点。引入 UUID 是区分它们的充要条件。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #comp/graph #concept/hashing #concept/solver
#ai/instruct
#task/domain/core #task/object/hasher #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 2: 修正 ShallowHasher 以避免哈希冲突

接下来，修改 `ShallowHasher`，使其在处理 `LazyResult` 类型的参数时包含 UUID。这能防止不同层级的递归任务因参数结构相似而被错误地哈希为同一个值。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return

        if isinstance(obj, Router):
~~~~~
~~~~~python
    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Must include UUID to distinguish different instances with similar structure
            # to prevent incorrect node merging (which causes cycles).
            self._hash_components.append(f"LAZY({obj._uuid})")
            return

        if isinstance(obj, Router):
~~~~~

### 下一步建议
运行 `python observatory/benchmarks/tco_performance.py`。预期结果是：
1.  `heavy_complex_countdown` 不再报错，能够正常完成。
2.  `NativeSolver` 的逻辑更加清晰和安全。
3.  我们可以继续推进“通用图结构缓存”的后续优化（Phase 4），届时我们可以基于修复后的图构建逻辑，实现真正的结构化缓存。
