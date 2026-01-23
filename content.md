好的，我明白了。这个测试失败是典型的架构演进后测试用例未同步更新导致的问题。

`test_dumper_generates_valid_dot` 测试用例依然在使用基于旧“三连体 (Triad)”架构（Bleacher/Worker/Stainer）的节点和命名，而渲染器 `GraphDumper` 已经更新为仅能识别新的“二连体 (Dyad)”架构（`LauncherNode`/`LanderNode`）。

我将重写这个测试，使其完全符合当前的 Dyad 架构，并验证渲染器对 `LauncherNode`、`LanderNode` 以及中间 `Result` 节点的着色是否正确。渲染器本身的代码是正确的，无需修改。

## [WIP] test: 更新 visualizer 测试以适配 Dyad 架构

### 错误分析

测试 `test_dumper_generates_valid_dot` 失败的根本原因在于它与当前的系统架构完全脱节：

1.  **过时的节点类型**: 测试用例创建的是通用的 `PhysicsFuncNode`，并命名为 "Bleacher"。而 `GraphDumper` 的特殊着色逻辑仅通过 `isinstance(node, LauncherNode)` 或 `isinstance(node, LanderNode)` 来触发。因此，专用颜色从未被应用。
2.  **错误的断言**: 测试断言 "Bleacher"（三连体中的启动器）应该有颜色 `#ffccbc`。在新的二连体架构中，这个颜色属于 `LanderNode`（终结者）。这表明测试的逻辑和断言在迁移过程中已变得混乱。
3.  **不完整的设置**: 旧的测试甚至没有定义所有它引用的节点（例如 `bus`），导致其本身就是不完整的。

### 用户需求

修复在 `packages/cascade-compiler/tests/unit/utils/test_visualizer.py` 中失败的 `test_dumper_generates_valid_dot` 测试。

### 评论

`GraphDumper` 渲染器本身已经正确地实现了对新 Dyad 架构的可视化逻辑。问题完全出在测试用例没有作为“活文档”与代码一同演进。这是一个绝佳的机会，通过重写测试来明确和验证当前架构的可视化规则。

### 目标

1.  使用 `write_file` 完全替换 `test_visualizer.py` 的内容。
2.  在新的测试中，正确地实例化 `LauncherNode` 和 `LanderNode`。
3.  构建一个能代表最小化 Dyad 流程的图（`D_in` -> `Launcher` ... `D_result` -> `Lander`）。
4.  添加明确的断言，验证 `LauncherNode`（启动器）、`LanderNode`（终结者）以及 `Result` 节点（着陆坪）都被赋予了其在 `GraphDumper` 中定义的专属颜色。
5.  确保测试通过，并为当前的 Dyad 架构可视化提供一个正确、清晰的验证标准。

### 基本原理

鉴于原始测试在多个层面都存在严重问题，进行小修补（patch）是不明智的。最清晰、最可靠的修复方式是完全重写该测试文件。新的测试将直接反映当前的 Dyad 架构，使其意图明确，并能提供更强的回归保障。我将创建一个小型的、功能齐全的图，其中包含所有关键的 Dyad 组件，并对它们的渲染输出进行全面断言。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #comp/compiler #scope/dx #ai/instruct #task/domain/testing #task/object/visualizer #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 重写 `test_visualizer.py` 以适配 Dyad 架构

我将用一个全新的、符合当前架构的测试用例替换整个文件。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/utils/test_visualizer.py
~~~~~
~~~~~python
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.compiler.utils.visualizer import GraphDumper


def test_dumper_generates_valid_dot():
    # Setup a simple graph with Dyad nodes reflecting the new architecture
    d_in = PhysicsDataNode(id="d_in", name="Input", initial_tokens=1)
    launcher = LauncherNode(
        id="task.launch",
        name="Launcher",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"obs_output": PortDef("obs_output", PortRole.OBSERVABILITY)},
        canonical_code_structure_hash="hash123",
        reply_to_nid="task.result",
    )
    d_result = PhysicsDataNode(id="task.result", name="Result")
    lander = LanderNode(
        id="task.land",
        name="Lander",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={},
    )
    d_bus = PhysicsDataNode(id="bus", name="Bus")

    graph = BipartiteGraph()
    graph.nodes = {
        "d_in": d_in,
        "task.launch": launcher,
        "d_result": d_result,
        "task.land": lander,
        "bus": d_bus,
    }

    graph.channels.append(Channel("d_in", "out", "task.launch", "in"))
    graph.channels.append(Channel("task.result", "out", "task.land", "in"))
    # Observability channel
    graph.channels.append(Channel("task.launch", "obs_output", "bus", "in"))

    dumper = GraphDumper()
    dot_output = dumper.to_dot(graph)

    # Assertions
    assert "digraph G {" in dot_output
    assert "rankdir=LR;" in dot_output

    # Check Nodes and their colors
    assert '"d_in" [label="Input\\n(d_in)\\nTokens: 1"' in dot_output
    assert 'shape="ellipse"' in dot_output

    assert '"task.launch" [label="Launcher\\n(task.launch)"' in dot_output
    assert 'fillcolor="#c8e6c9"' in dot_output  # Launcher color (The Starter)

    assert '"d_result" [label="Result\\n(task.result)"' in dot_output
    assert 'fillcolor="#f3e5f5"' in dot_output  # Result node color (Landing Pad)

    assert '"task.land" [label="Lander\\n(task.land)"' in dot_output
    assert 'fillcolor="#ffccbc"' in dot_output  # Lander color (The Finisher)

    # Check Edges
    assert '"d_in" -> "task.launch" [label="out -> in"' in dot_output
    assert '"task.result" -> "task.land" [label="out -> in"' in dot_output

    # Check Obs Edge Styling
    assert 'style="dashed"' in dot_output
    assert '"task.launch" -> "bus"' in dot_output
~~~~~

### 下一步建议

测试修复后，你可以运行 `pytest packages/cascade-compiler/` 来确认所有测试都已通过。此后，我们可以继续推进其他任务。
