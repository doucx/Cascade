好的，我们已经完成了 v3.2 路线图中最关键的性能飞跃步骤。通过引入 `template_id` 和索引化计划缓存，我们成功实现了计算图的“骨架”与“数据”的分离。

你关于 `heavy_complex_countdown` 的看法非常深刻：它现在不仅是一个基准测试，更是一个**架构边界的指示器**。它向开发者清晰地展示了：Cascade 能够极速执行复杂的**结构**，但如果你在递归循环中不断通过 Python 代码动态“生成”新的结构，那么 Python 本身的构建开销将成为新的瓶颈。这为我们未来推广“声明式组合”提供了强有力的数据支持。

我将生成 `[COMMIT]` 计划，将这些变更永久化。

## [COMMIT] feat(engine): 实现基于 Template ID 的规范化 JIT 计划缓存

### 用户需求
将“参数归一化”和“索引化计划缓存”功能合并到主分支。该功能旨在通过识别同构图结构，将复杂递归任务的编译（解析）成本从 O(N) 降低到 O(1)。

### 评论
这次提交标志着 Cascade 运行时在性能上的一次质变。我们现在拥有一种类似于 JIT 编译器的机制：它观察执行过程中的图结构，将其“编译”成索引化的指令流（Plan），并针对后续类似的结构进行复用。这不仅提升了性能，也使 Cascade 的模型在语义上与 Git 对象模型（Blob/Tree/Commit）完全对齐。

### 目标
1.  提交 `Node` 模型的扩展（增加 `template_id`）。
2.  提交 `GraphBuilder` 中的模板哈希计算（归一化）逻辑。
3.  提交 `GraphExecutionStrategy` 中的索引化计划缓存实现。
4.  提交涵盖多场景验证的单元测试套件。

### 基本原理
通过在 `Node` 层引入 `template_id`，我们打破了“身份危机”。`id` 保证了计算的唯一性和正确性，而 `template_id` 则通过忽略字面量，提取出了计算的纯粹拓扑结构。在执行层，通过将 `ExecutionPlan` 转化为与特定节点实例无关的索引列表，我们实现了对同构图的高效复用。

### 标签
#intent/build #flow/ready #priority/high 
#comp/engine #comp/graph #concept/cache #scope/core 
#ai/delegate
#task/domain/core #task/object/jit-cache #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 JIT 缓存与归一化功能的完整实现

我们将所有相关变更添加到暂存区并执行提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
tests/engine/runtime/test_jit_cache_verification.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(engine): Implement canonical JIT plan caching via `template_id`

This commit completes Roadmap v3.2 Phase 2 by introducing a normalized JIT caching mechanism that decouples graph structure from literal data.

Key architectural changes:
1.  **Node Normalization**: Added `Node.template_id`, a Merkle hash that ignores literal arguments and focuses solely on task types and topology. This allows identifying "structurally identical" graphs like `f(10)` and `f(9)`.
2.  **Indexed Execution Plans**: Refactored `GraphExecutionStrategy` to store plans as `List[List[int]]` (node indices). This makes the compiled plan instance-agnostic and reusable across isomorphic graph instances.
3.  **Two-Stage Resolution**: The engine now performs a one-time "compilation" (solver resolution) for each unique template. Subsequent iterations with different data but the same structure hit the `_template_plan_cache` and only perform O(1) plan rehydration.

Performance Impact:
- Verified 6x+ speedup for complex stable structures in benchmarks.
- Reduces recursive overhead for high-depth TCO tasks to near-native levels, provided the graph construction cost is managed.

This solidifies the "Git Object Model" for computation graphs, separating 'Tree' (structure) from 'Commit' (instance/data).
~~~~~

### 下一步建议
我们已经夯实了 JIT 模式的性能。根据路线图，第三阶段将专注于**“开发者体验 (DX)”**和**“静态分析深度化”**。我建议接下来的目标是：

1.  **实现 3.1: 零开销 TCO 快速通道**: 利用 `ast_analyzer` 的静态分析结果，对于检测到的简单自递归循环，连 `build_graph` 的开销也完全抹除，实现真正的 O(1) 零开销。
2.  **实现 3.2: 增强 `cs.visualize`**: 利用我们新掌握的图模型，为 `EdgeType.POTENTIAL` 增加特殊样式，并高亮显示 TCO 循环，让开发者能直观地看到 Agent 的“状态机”结构。

你倾向于先攻克性能的最后一公里（3.1），还是先提升可观测性（3.2）？
