好的，我们已经成功实现了递归静态分析和循环检测，并优化了分析过程中的缓存机制。最新的基准测试结果（8.66s）证明，在增加了强大的递归分析能力的同时，我们并没有对现有的执行性能产生负面影响（即“静态分析税”已被缓存机制完美抵消）。

现在我们将这一系列改动作为一个完整的逻辑单元提交。

## [COMMIT] feat(engine): implement zero-overhead TCO for multi-task cycles

### 用户需求
Cascade 需要能够识别并优化复杂的多任务递归循环（如 `A -> B -> A`），使其在性能上与简单的自递归保持一致。

### 评论
这次提交标志着 Cascade 静态分析能力的一次重大跃进。通过引入递归 AST 分析和强连通分量识别，我们现在可以在执行前准确地“看透” Agent 的状态机结构。更重要的是，通过在 Task 级别引入解析缓存，我们确保了这种强大的静态分析能力是“廉价”的，不会拖慢动态工作流的构建速度。

### 目标
提交包含递归静态分析、循环标记、Solver 过滤逻辑优化以及 Zero-Overhead 快速通道的完整实现。

### 基本原理
我们通过在 `GraphBuilder` 阶段识别循环并分配 `tco_cycle_id`，在 `GraphExecutionStrategy` 中建立了一个基于 ID 对齐的快速通道。该通道允许引擎跳过结构哈希，直接通过任务标识符命中图模板，从而将复杂循环的开销从 O(N) 降低到 O(1)。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/graph #concept/tco #scope/core #ai/instruct #task/domain/engine #task/object/tco-loop #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 TCO 循环优化相关改动

我们将修改后的模型定义、分析器、构建器、执行策略以及相应的测试用例添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-engine/src/cascade/adapters/solvers/native.py
tests/engine/runtime/test_tco_mutual_recursion.py
tests/engine/graph/test_build_tco.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(engine): implement zero-overhead TCO for multi-task cycles

This commit introduces recursive static analysis and cycle detection to enable zero-overhead Tail Call Optimization (TCO) for complex Agent loops (e.g., A -> B -> A).

Key changes:
1.  **Recursive AST Analysis**: Enhanced `ast_analyzer` to recursively track `return` call chains across tasks.
2.  **Cycle Detection**: Implemented a DFS-based algorithm to identify Strongly Connected Components (cycles) in the task call graph, assigning a stable `_tco_cycle_id` to involved tasks.
3.  **Static Analysis Caching**: Added Task-level caching for AST parsing results to eliminate redundant analysis overhead during iterative graph builds.
4.  **Zero-Overhead Fast Path**: Updated `GraphExecutionStrategy` to utilize `tco_cycle_id` for O(1) template lookups, bypassing `StructuralHasher` for tasks within a recognized loop.
5.  **Solver Refinement**: Updated `NativeSolver` to correctly ignore `POTENTIAL` edges during topological sorting, preventing false cycle detections.
6.  **Recursive Visualization Foundation**: `GraphBuilder` now constructs a recursive shadow graph, providing the metadata needed for full state-machine visualization in `cs.visualize`.

These optimizations bring the performance of multi-task Agent loops to nearly equal that of simple self-recursion and raw imperative loops.
~~~~~

### 下一步建议
我们已经夯实了底层性能和分析基础。接下来我建议：
1.  **增强可视化**: 更新 `cs.visualize` 以利用 `POTENTIAL` 边和 `tco_cycle_id` 渲染出闭环的状态机图，这是向用户展示递归分析价值的最直观方式。
2.  **通用图结构缓存 (Generalizing Structural Caching)**: 目前快速通道仅限“简单任务”。我们可以尝试放宽限制，让包含静态依赖但结构稳定的复杂子图也能通过 `StructuralHasher` 命中缓存，从而进一步降低“慢速通道”的开销。
