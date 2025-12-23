好的，你的分析非常敏锐。仅仅黑名单 `POTENTIAL` 边是不够的，这说明我的初步诊断过于简单了。当系统中存在多种类型的“元数据”边时，黑名单策略会变得非常脆弱。

你说得对，我们必须切换到一个更健壮的白名单策略，明确地告诉 `Solver` 哪些边类型代表了**真正的执行依赖**。这不仅能修复当前的 Bug，还能让系统对未来新增的、非执行类型的边（例如用于可视化或静态分析的边）更有弹性。

我将生成一个计划来实现这个修改。

## [WIP] fix(engine): Use whitelist in NativeSolver to ignore metadata edges

### 错误分析
你正确地指出了，`NativeSolver` 中现有的、用于忽略 `EdgeType.POTENTIAL` 边的黑名单式检查，并未能解决 `heavy_complex_countdown` 基准测试中的循环检测错误。

根本原因在于，`NativeSolver` 的默认逻辑过于宽容：它将图中几乎所有类型的边都视为拓扑排序的依据。随着架构演进，我们引入了更多用于静态分析和元数据表达的边类型（如 `POTENTIAL`），它们描述的是“未来的”或“可能的”关系，而非“当前的”执行先决条件。

黑名单策略是脆弱的，因为它要求我们每次添加新的元数据边类型时，都必须记得更新所有 Solver。切换到白名单策略，将“什么边是执行依赖”这个契约显式化，从而一劳永逸地解决了这个问题。

### 用户需求
修复在运行 `heavy_complex_countdown` 基准测试时出现的 `ValueError: Cycle detected` 错误。通过修改 `NativeSolver`，使其只考虑构成直接执行依赖的边类型，忽略所有用于静态分析或元数据的边。

### 评论
这是一个关键的架构加固。将 Solver 的关注点严格限制在执行依赖上，可以有效解耦“执行规划”和“静态分析”这两个不同层面的逻辑。这使得我们未来可以自由地向图中添加更丰富的元数据，而无需担心破坏核心的运行时调度，极大地提升了系统的健壮性和可扩展性。

### 目标
1.  在 `native.py` 中定义一个包含所有“执行依赖”边类型的白名单集合 (`EXECUTION_EDGE_TYPES`)。
2.  修改 `NativeSolver.resolve` 方法中的循环逻辑，使其只处理边类型在该白名单中的边。
3.  确保修改后 `tco_performance.py` 基准测试能够成功运行。

### 基本原理
Solver 的核心职责是为**当前**的计算步骤生成一个无环的执行计划。用于静态分析的边（如 `POTENTIAL`）描述的是**未来**可能发生的调用，它们不应影响当前步骤的拓扑结构。通过创建一个只包含 `DATA`, `CONDITION`, `SEQUENCE` 等明确表示执行先决条件的边类型的白名单，我们可以确保 Solver 的输入是纯粹和正确的，从而根除此类因元数据污染导致的循环错误。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #concept/state #scope/core
#ai/instruct
#task/domain/testing #task/object/solver #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 在 NativeSolver 中实现边类型白名单

我们将修改 `cascade-engine` 包中的 `native.py` 文件。旧的逻辑是黑名单 `POTENTIAL` 边，新的逻辑将是只允许一个明确的执行相关边类型集合。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
        for edge in graph.edges:
            # --- CRITICAL FIX ---
            # Ignore potential edges during topological sort. They are metadata for
            # static analysis and caching, not execution dependencies for the current step.
            if edge.edge_type == EdgeType.POTENTIAL:
                continue

            adj[edge.source.id].append(edge.target)
            in_degree[edge.target.id] += 1
~~~~~
~~~~~python
        # Whitelist of edge types that represent actual execution dependencies.
        # This prevents metadata edges (like POTENTIAL) from creating cycles.
        EXECUTION_EDGE_TYPES = {
            EdgeType.DATA,
            EdgeType.CONDITION,
            EdgeType.CONSTRAINT,
            EdgeType.IMPLICIT,
            EdgeType.SEQUENCE,
            EdgeType.ROUTER_ROUTE, # Considered a dependency for plan completeness
        }

        for edge in graph.edges:
            if edge.edge_type not in EXECUTION_EDGE_TYPES:
                continue

            adj[edge.source.id].append(edge.target)
            in_degree[edge.target.id] += 1
~~~~~

### 下一步建议

1.  **验证修复**: 请重新运行 `python observatory/benchmarks/tco_performance.py` 基准测试，确认 `heavy_complex_countdown` 部分能够成功完成。
2.  **创建回归测试**: 建议为 `NativeSolver` 创建一个专门的单元测试。该测试可以手动构建一个包含所有 `EdgeType` 的图（包括 `POTENTIAL` 和其他未来可能添加的元数据类型），并断言 `resolve()` 方法生成的计划只受到了 `EXECUTION_EDGE_TYPES` 中定义的边的影响。这将确保此逻辑在未来不会被意外破坏。
