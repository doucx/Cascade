好的，所有的测试都已经通过。这意味着我们不仅完成了 `visualize` 的功能增强，还通过对 `GraphBuilder` 的重构，让 Cascade 的静态图结构变得更加准确和健壮。

现在，我将生成一个 `[COMMIT]` 计划，将这些改进作为一个完整的逻辑单元提交。

## [COMMIT] feat(sdk): 通用化显式跳转的可视化渲染

### 用户需求
用户需要 `cs.visualize` 工具能够准确地展示包含显式跳转 (`cs.Jump`, `cs.bind`) 的复杂工作流拓扑，包括自引用循环和多节点循环。

### 评论
这是一个重要的里程碑。通过这一改动，我们将 `ITERATIVE_JUMP` 从一个仅用于运行时的“黑盒”占位符，提升为了静态图中完全透明、拓扑正确的“一等公民”。这不仅极大地提升了开发者在构建复杂状态机时的观测效率，也为未来更高层次的图分析和优化奠定了基础。

### 目标
创建一个 Git 提交，包含对 `GraphBuilder` 拓扑构建逻辑的通用化重构、`visualize` 渲染器的样式增强，以及完整的 TDD 测试套件。

### 基本原理
我们遵循了“单一真相来源”的原则，将跳转逻辑的解析工作从渲染器移回了 `GraphBuilder`。这使得图本身就能准确反映潜在的控制流转移。渲染器随后根据边类型应用一致的视觉样式。这种架构上的清晰性也反映在我们的测试套件中，它现在涵盖了从简单自循环到复杂循环路径的多种场景。

### 标签
#intent/build #flow/ready #priority/high #comp/graph #comp/sdk #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交可视化增强功能

将涉及图构建、可视化渲染以及测试用例的修改添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-graph/src/cascade/graph/build.py
packages/cascade-sdk/src/cascade/tools/visualize.py
tests/sdk/tools/test_visualize.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(sdk): Generalize visualization of explicit iterative jumps

Enhanced 'cs.visualize' and 'GraphBuilder' to correctly represent and render explicit control flow transitions created via 'cs.bind' and 'cs.Jump'.

Key Changes:
1. **GraphBuilder**: Refactored ITERATIVE_JUMP edge creation to move away from placeholders. It now iterates through all routes in a 'JumpSelector' and creates distinct, topologically correct edges for each jump target. The jump key (e.g., "next", "restart") is now stored as the edge's 'arg_name'.
2. **Visualize**: Updated to use the correct target and label (from 'arg_name') provided by the edge object. Iterative jumps are now rendered as bold blue edges, regardless of whether they are self-referencing or point to upstream nodes.
3. **Tests**: Added comprehensive TDD cases in 'test_visualize.py' covering self-loops and multi-node cycles (e.g., A -> B -> C -> A), verifying both the structure and the dynamic labels.

This ensures that the static graph representation of a workflow perfectly matches its potential runtime execution paths, providing superior observability for complex state machines.
~~~~~

### 下一步建议
我们已经完成了可视化的升级。根据路线图，现在的 Cascade 已经具备了显式状态转移的能力，并且它是可观测的。

为了进一步释放这个新架构的潜力，我建议下一步我们考虑 **`cs.select_jump` 的动态化增强**。目前它的路由表是静态的，如果我们允许根据前序任务的结果来动态决定跳转目标，Cascade 将能实现更复杂的动态分支策略。或者，我们可以开始实现 **阶段四：统一的双层身份体系**，为后续的执行计划缓存做准备。你倾向于哪个方向？
