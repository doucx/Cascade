from cascade.compiler.utils.visualizer import GraphDumper
from cascade.spec.physical.dyad import LanderNode, LauncherNode
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel


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
