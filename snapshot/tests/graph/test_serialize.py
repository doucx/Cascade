import json
import pytest
import cascade as cs
from cascade.graph.build import build_graph
from cascade.graph.serialize import to_json, from_json, graph_to_dict

# --- Fixtures for Testing ---

@cs.task
def simple_task(x):
    return x + 1

@cs.task
def another_task(y):
    return y * 2

def test_serialize_basic_graph():
    """Test serializing a simple linear graph."""
    target = another_task(simple_task(x=10))
    graph = build_graph(target)

    json_str = to_json(graph)
    data = json.loads(json_str)

    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1

    # Check Node Data
    node_names = {n["name"] for n in data["nodes"]}
    assert "simple_task" in node_names
    assert "another_task" in node_names

    # Check Callable Metadata
    node_simple = next(n for n in data["nodes"] if n["name"] == "simple_task")
    assert node_simple["callable"]["qualname"] == "simple_task"
    # Note: local functions might have issues with importlib if not top-level, 
    # but for structure check it's fine.

def test_round_trip_top_level_functions():
    """
    Test full round-trip (serialize -> deserialize) with top-level functions.
    Only top-level functions can be reliably pickled/imported.
    """
    # We use the top-level tasks defined in this module
    target = another_task(simple_task(x=5))
    original_graph = build_graph(target)

    # Serialize
    json_str = to_json(original_graph)

    # Deserialize
    restored_graph = from_json(json_str)

    assert len(restored_graph.nodes) == len(original_graph.nodes)
    assert len(restored_graph.edges) == len(original_graph.edges)

    # Verify function restoration
    restored_node = next(n for n in restored_graph.nodes if n.name == "simple_task")
    assert restored_node.callable_obj == simple_task.func
    assert restored_node.callable_obj(1) == 2

def test_serialize_params():
    """Test serialization of Param nodes."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph = build_graph(target)

    data = graph_to_dict(graph)
    param_node = next(n for n in data["nodes"] if n["node_type"] == "param")
    
    assert param_node["param_spec"]["name"] == "env"
    assert param_node["param_spec"]["default"] == "dev"
    assert param_node["param_spec"]["description"] == "Environment"

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.node_type == "param")
    assert p_node.param_spec.name == "env"

def test_serialize_with_retry():
    """Test serialization of retry policy."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0)
    graph = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")

    assert task_node["retry_policy"]["max_attempts"] == 5
    assert task_node["retry_policy"]["delay"] == 1.0

    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5