好的，测试全部通过，这标志着我们已经成功地将静态分析功能集成进来，并解决了它带来的严重副作用。现在是时候将这个里程碑作为一个原子单元提交了。

我将生成一个 `[COMMIT]` 计划来固化这些变更。

## [COMMIT] feat(graph): 引入 TCO 静态分析并隔离其对运行时的影响

### 用户需求
1.  实现一个基于 AST 的静态分析器，用于在不执行代码的情况下，预测和发现 `@cs.task` 中潜在的尾递归调用（TCO）路径。
2.  在图构建阶段，将这些潜在路径表示为新的 `POTENTIAL` 边和“影子节点”，以增强图的可视化透明度。
3.  修复因引入影子节点而导致的 TCO 失效和参数注入错误。
4.  创建一个 Git 提交来记录这一系列完整的变更。

### 评论
这是一次教科书式的“功能引入与架构加固”并行的操作。我们成功地为 Cascade 增加了一项业界领先的、极具价值的静态分析能力，能够“看透”动态 Agent 的未来走向。但更重要的是，我们通过在 Solver 和 Strategy 层面建立清晰的边界，确保了这种“观测”能力完全不会干扰到引擎的“执行”稳定性。这份提交不仅交付了一个新功能，更巩固了 Cascade 架构的健壮性。

### 目标
将所有与 AST 分析器实现、图构建器集成、运行时隔离修复以及相关测试相关的变更，作为一个逻辑完整的单元提交到版本控制中。

### 基本原理
我们已经完成了从功能实现到问题修复的整个闭环，并通过了完整的测试验证。现在，将这些变更合并到一个独立的、具有清晰描述的提交中，是保证代码库历史干净、可追溯的最佳实践。

### 标签
#intent/build #intent/fix #flow/ready #priority/high #comp/graph #comp/engine #concept/state #scope/core #ai/instruct #task/domain/engine #task/object/solver #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 暂存所有相关变更

我们将 `git status` 中列出的所有新文件和修改过的文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
packages/cascade-engine/src/cascade/adapters/solvers/native.py
packages/cascade-engine/src/cascade/runtime/strategies.py
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-sdk/src/cascade/tools/visualize.py
packages/cascade-spec/src/cascade/graph/model.py
tests/engine/graph/test_ast_analyzer.py
tests/engine/graph/test_build_tco.py
~~~~~

#### Acts 2: 提交功能与修复

现在，我们创建一个内容详尽的提交，清晰地记录新功能的引入、它引发的问题以及最终的解决方案。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(graph): Introduce static TCO analysis and isolate it from runtime

Introduces a static analyzer for Tail Call Optimization (TCO) paths using Python's `ast` module. This significantly enhances graph transparency by visualizing potential state transitions before execution.

This new capability added "shadow nodes" and `POTENTIAL` edges to the graph, which initially caused two critical regressions:
1.  **TCO Failure & Resource Leaks:** The Solvers incorrectly included shadow nodes in the execution plan, breaking the TCO loop and preventing timely resource release.
2.  **Argument Injection Failure:** `GraphExecutionStrategy` wrongly assumed the last node in the graph was the target, causing `TypeError` as initial parameters were injected into parameter-less shadow nodes.

This commit resolves these issues by strictly isolating static analysis metadata from the runtime execution path:
-   **Solver Isolation:** `NativeSolver` and `CSPSolver` are updated to explicitly filter out shadow nodes and ignore `POTENTIAL` edges when generating the execution plan.
-   **Target Fix:** `GraphExecutionStrategy` is corrected to robustly locate the root node using `graph.nodes[0]`, which is guaranteed by the top-down build process.

With these changes, the engine's stability and TCO guarantees are fully restored, while developers gain the full benefit of enhanced static graph observability.
~~~~~

### 当前阶段分析与下一步建议

**当前阶段分析：**

我们已经成功完成了**“路线图：基于身份对齐的静态分析集成”**中的**第一阶段（Regression Fix）**。

-   我们引入了 AST 静态分析这一核心能力。
-   我们通过“边语义剪枝”（修改 Solver）和“精确目标节点定位”（修改 Strategy），彻底修复了它带来的严重回归问题。
-   目前，引擎既拥有了静态分析的“远见”，又保持了动态执行的“稳健”。我们的架构边界是清晰和安全的。

**下一步建议：**

现在基础已经稳固，我们可以进入路线图的第二和第三阶段，将这项新能力转化为真正的用户价值和更好的代码质量。我建议从以下两个方向中选择一个作为下一步：

1.  **选项 A (进入第二阶段 - 架构优化):**
    *   **任务**: 实现 **“稳定身份标识符演进”**。具体来说，是在 `Node` 数据模型中增加一个 `is_shadow: bool = False` 字段。
    *   **价值**: 让 Solver 的过滤逻辑从“检查边类型”变为“检查节点属性”，这在代码上更清晰、更类型安全，也更高效。这是一个提升内部代码质量的“健康度”任务。

2.  **选项 B (进入第三阶段 - 能力释放):**
    *   **任务**: 实现 **“全景透明度可视化”**。具体来说，是增强 `cs.visualize` 的渲染逻辑。
    *   **价值**: 让用户能直观地看到静态分析的结果。例如，用**虚线和红色**来绘制 `POTENTIAL` 边，用**半透明或灰色**的样式来渲染影子节点。这将使 `visualize` 的输出信息量极大丰富，直接将新功能的价值交付给用户。

我个人更**推荐选项 B**，因为它能让我们最快地“看到”我们的劳动成果，并获得直观的反馈。

请确认你的选择，我将为你生成相应的计划。
