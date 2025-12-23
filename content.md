太棒了，测试通过证明了我们的重构是正确且安全的。现在，我们将把这个重要的代码质量提升作为一个原子提交固化下来。

## [COMMIT] refactor(spec): 在 Node 模型中引入 is_shadow 标志

### 用户需求
将“影子节点”的识别方式从依赖图拓扑（检查 `POTENTIAL` 边）重构为依赖节点自身的显性属性（`node.is_shadow`），并创建一个 Git 提交来记录这一变更。

### 评论
这次重构是“显式优于隐式”设计哲学的完美体现。通过在 `Node` 数据模型中添加 `is_shadow` 标志，我们将节点的身份从一个需要通过上下文推断的*隐性状态*，转变为一个自包含的*显性属性*。这极大地解耦了图的构建器与消费者（Solver, Visualizer），使代码更清晰、更健壮，也更易于未来的维护和扩展。

### 目标
创建一个原子化的 Git 提交，包含对 `Node` 模型的修改，以及 `GraphBuilder`、`solvers` 和 `visualize` 工具对这一新标志的适配。

### 基本原理
重构已经完成，并通过了完整的测试套件验证。现在将其作为一个逻辑单元提交，可以确保代码库历史的清晰性，并为后续基于此优化的功能开发提供一个稳定的基础。

### 标签
#intent/refine #flow/ready #priority/medium #comp/spec #comp/engine #comp/sdk #scope/core #scope/dx #ai/instruct #task/domain/engine #task/object/node-model #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存所有重构相关的变更

我们将所有修改过的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/graph/model.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-engine/src/cascade/adapters/solvers/native.py
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~

#### Acts 2: 提交重构

现在，我们创建一个内容详尽的提交，解释这次重构的动机和实现。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(spec): Introduce is_shadow flag to Node model

Refactors the mechanism for identifying "shadow nodes" (nodes for static analysis) from an implicit, topology-based check to an explicit flag on the `Node` model itself.

Previously, components like Solvers had to inspect incoming `POTENTIAL` edges to infer if a node was a shadow node. This tightly coupled the consumers of the graph with the implementation details of the `GraphBuilder`.

Changes:
1.  **`cascade.graph.model.Node`**: A new `is_shadow: bool` field is added.
2.  **`GraphBuilder`**: Now explicitly sets `is_shadow=True` when creating nodes for static TCO analysis.
3.  **Solvers (`native`, `csp`)**: Refactored to use the simple `if not node.is_shadow` check, which is cleaner, more efficient, and decouples them from edge-type logic.
4.  **`visualize` Tool**: Also updated to use the `node.is_shadow` flag for styling, simplifying its logic.

This change significantly improves code health and developer experience by making the node's identity self-contained and explicit, adhering to the "explicit is better than implicit" principle.
~~~~~

### 当前阶段分析与下一步建议

**当前阶段分析：**

我们已经成功完成了**“路线图：基于身份对齐的静态分析集成”**中的**第二阶段（Blueprint Stability / 架构优化）**。

-   **已完成**: 我们不仅将静态分析的能力完整、安全地集成，并且通过这次重构，使其实现方式变得更加优雅和健壮。代码的“技术债务”得到了有效控制。
-   **当前状态**: 我们的架构现在处于一个非常健康的状态。静态分析功能本身已经可用、可见，并且其内部实现也已经过优化。

**下一步建议：**

现在，我们的基础非常稳固，是时候利用这个强大的静态分析能力来构建新的、有价值的用户功能了。我建议我们继续**第三阶段（Value Realization / 能力释放）**：

-   **任务**: 实现 **“静态循环检测 (`StaticCycleGuard`)”**。
-   **价值**: 利用我们已经拥有的 `POTENTIAL` 边信息，在 `dry_run` 或一个新的 `cs.lint` 工具中，检测出静态的死循环（例如，任务A返回任务B，任务B又返回任务A），并在代码实际运行前向用户发出警告。这将极大地提升 Cascade 的“静态治理”和“主动安全”能力，防止开发者无意中创建出无限循环的 Agent。

如果你同意，我将为你生成实现静态循环检测的计划。
