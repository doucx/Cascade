好的，我们已经确认了 `test_visualize_with_list_of_lazy_results` 失败，将 `visualize` 的开发周期带入了 "RED" 状态。

现在，我将生成计划来修改 `visualize.py`，使其与 `run()` 的行为保持一致，从而让测试通过。

## [WIP] feat: Add auto-gathering support to cs.visualize

### 用户需求
`cs.visualize()` 函数需要支持接收 `LazyResult` 对象的列表或元组作为其 `target` 参数，并为这个隐式并行工作流生成正确的图表示。

### 评论
这是一次重要的 API 一致性重构。通过使 `visualize` 和 `run` 接受相同的输入类型，我们降低了用户的学习成本，并强化了 Cascade API 的一致性和直观性。用户现在可以确信，任何可以 `run` 的目标，也都可以被 `visualize`。

### 目标
1.  修改 `cascade.tools.visualize.visualize` 函数。
2.  在函数内部，检查 `target` 参数是否为列表或元组。
3.  如果是，则使用内部的 `_internal_gather` 任务将其包装成一个单一的 `LazyResult` 根节点。
4.  处理空列表的边缘情况，为其返回一个有效的空图 DOT 字符串。

### 基本原理
我们将复用为 `cs.run` 开发的自动汇合模式。通过在 `visualize` 函数的入口处添加一个简单的类型检查和包装逻辑，我们可以将列表/元组输入转换为 `build_graph` 函数可以理解的单一根节点。这个改动被完全隔离在 `visualize` 函数内部，不会影响图构建或引擎的核心逻辑，是一个低风险、高回报的改进。

### 标签
#intent/build #flow/ready #priority/medium #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/sdk #task/object/visualize #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 `visualize` 中实现自动汇合逻辑

我们将修改 `visualize.py`，添加处理列表和元组输入的逻辑。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
from typing import Any
from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType


def visualize(target: Any) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph, _ = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
~~~~~
~~~~~python
from typing import Any
from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType
from cascade.internal.inputs import _internal_gather


def visualize(target: Any) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    if isinstance(target, (list, tuple)):
        if not target:
            # Return an empty graph for an empty list
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])
        workflow_target = _internal_gather(*target)
    else:
        workflow_target = target

    graph, _ = build_graph(workflow_target)

    dot_parts = [
        "digraph CascadeWorkflow {",
~~~~~

### 下一步建议

我们已经实现了 `visualize` 函数的自动汇合逻辑。请重新运行测试套件。我预期 `tests/sdk/tools/test_visualize.py` 中的所有测试现在都应该通过，将我们的 TDD 周期推进到 "GREEN" 状态。

在此之后，整个“自动汇合语法糖”功能就已完全实现并经过测试。我建议我们可以创建一个最终的 `[COMMIT]` 计划，将这个功能的所有相关变更（TDD 测试、核心实现、重构和可视化支持）合并到一个原子提交中。
