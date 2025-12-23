好的，既然基准测试和回归测试均已顺利通过，这标志着我们成功解决了“结构-数据分离”重构后最隐蔽的两个图逻辑漏洞。

关于你提到的微小性能变化，这主要是由于 `NativeSolver` 增加了白名单过滤开销，以及 `ShallowHasher` 处理 UUID 带来的额外字符串拼接成本。但在这种极致的性能压测下，这种量级的开销是确保逻辑正确性的必要代价。

我将生成最终的 `[COMMIT]` 计划。

## [COMMIT] fix(engine): 解决图构建中的哈希冲突与影子节点执行问题

### 错误分析
本次修复针对的是在处理复杂递归任务时（如 `heavy_complex_countdown`）出现的 `ValueError: Cycle detected` 错误。

1.  **哈希冲突 (真环)**: `ShallowHasher` 之前对嵌套 `LazyResult` 采用固定占位符，导致不同生命周期的任务实例在注册表中被错误合并，形成了物理上的数据依赖环。
2.  **元数据干扰 (假环)**: `NativeSolver` 将 `POTENTIAL` 边误认为执行依赖，导致拓扑排序失败。
3.  **影子节点调度 (崩溃)**: 在忽略元数据边后，仅用于分析的影子节点变成孤立节点并被推入执行队列，因缺少可执行体导致 `TypeError`。

### 用户需求
确保 Cascade 能够稳定处理复杂的、带有深度递归和动态依赖的计算图，并维持 TCO 优化的正确性。

### 评论
这次修复是“结构数据分离”架构走向成熟的关键一步。它确立了两个重要的原则：首先，执行调度必须严格基于“执行依赖白名单”；其次，节点的 Interning（去重）必须以保证实例唯一性为前提。这为后续实现更激进的 Hashlife 风格缓存奠定了稳固的安全基石。

### 目标
1.  提交对 `NativeSolver` 的改进，增加边类型白名单并彻底过滤影子节点。
2.  提交对 `ShallowHasher` 的改进，引入 UUID 区分不同的 `LazyResult` 实例。

### 基本原理
通过将“元数据（分析用）”与“执行数据（调度用）”在 Solver 层级进行显式隔离，并提高哈希的区分度，我们消除了图拓扑结构中的所有歧义。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/engine #comp/graph #concept/hashing #concept/solver #scope/core 
#ai/delegate
#task/domain/core #task/object/graph-execution #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交图逻辑修复代码

我们将修改后的 `NativeSolver` 和 `ShallowHasher` 逻辑提交到仓库，标志着本次问题的圆满解决。

~~~~~act
git_add
packages/cascade-engine/src/cascade/adapters/solvers/native.py
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): resolve dependency cycles and shadow node execution

This commit fixes critical issues in the execution graph logic that caused `ValueError: Cycle detected` during complex recursive tasks:

1.  **Execution Edge Whitelist**: `NativeSolver` now uses a whitelist of edge types (`DATA`, `CONDITION`, etc.) for topological sorting. This prevents metadata edges like `POTENTIAL` (used for static analysis) from interfering with the runtime execution plan.
2.  **Shadow Node Filtering**: `NativeSolver` now explicitly filters out shadow nodes (`is_shadow=True`) from the execution plan, preventing attempts to execute non-runnable analysis nodes.
3.  **Hash Collision Prevention**: Updated `ShallowHasher` to include the `_uuid` of `LazyResult` arguments. This prevents unrelated task instances from being incorrectly merged into the same graph node, which previously created real dependency cycles.

These changes stabilize the Graph/JIT path for complex recursive workflows and long-running agents.
~~~~~

### 下一步建议
- **性能巡检**: 虽然 103x 的加速已经非常可观，但如果未来对 `Graph/JIT` 路径有更高的 TPS 要求，我们可以考虑将 `NativeSolver` 的白名单过滤逻辑下移到 C/Rust 层级。
- **完善静态分析**: 现在 Solver 已经可以安全处理影子节点，我们可以开始尝试在可视化工具中更好地展示这些 `POTENTIAL` 边，帮助开发者直观理解递归 Agent 的行为。
