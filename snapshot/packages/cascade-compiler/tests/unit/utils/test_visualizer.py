from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.compiler.utils.visualizer import GraphDumper


def test_dumper_generates_valid_dot():
    # Setup a simple graph
    d1 = PhysicsDataNode(id="d1", name="Data1", initial_tokens=1)
    f1 = PhysicsFuncNode(id="task.bleach", name="Bleacher")
    f2 = PhysicsFuncNode(id="task.worker", name="Worker")

    graph = BipartiteGraph()
    graph.nodes = {"d1": d1, "task.bleach": f1, "task.worker": f2}

    graph.channels.append(Channel("d1", "out", "task.bleach", "in"))
    graph.channels.append(
        Channel("task.bleach", "worker_input", "task.worker", "in", tag_filter="XYZ")
    )
    # Observability channel
    graph.channels.append(Channel("task.bleach", "obs_output", "bus", "in"))

    dumper = GraphDumper()
    dot_output = dumper.to_dot(graph)

    # Assertions
    assert "digraph G {" in dot_output
    assert "rankdir=LR;" in dot_output

    # Check Nodes
    assert '"d1" [label="Data1\\n(d1)\\nTokens: 1"' in dot_output
    assert 'shape="ellipse"' in dot_output
    assert '"task.bleach" [label="Bleacher\\n(task.bleach)"' in dot_output
    # Check heuristic coloring
    assert 'fillcolor="#ffccbc"' in dot_output  # Bleacher color

    # Check Edges
    assert '"d1" -> "task.bleach" [label="out -> in"' in dot_output
    assert '"task.bleach" -> "task.worker"' in dot_output
    assert 'label="worker_input -> in\\n[XYZ]"' in dot_output

    # Check Obs Edge Styling
    assert 'style="dashed"' in dot_output
