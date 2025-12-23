import json
import cascade as cs
from cascade.graph.build import build_graph
from cascade.graph.serialize import to_json, from_json, graph_to_dict

# --- Top-Level Tasks for Serialization Testing ---


@cs.task
def simple_task(x):
    return x + 1


@cs.task
def another_task(y):
    return y * 2


@cs.task
def t_condition():
    return True


@cs.task
def t_dynamic_constraint(val):
    return val


@cs.task
def t_target(x):
    return x


# --- Tests ---


def test_serialize_basic_graph():
    """Test serializing a simple linear graph."""
    target = another_task(simple_task(x=10))
    graph, _, _ = build_graph(target)

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
    original_graph, _, _ = build_graph(target)

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
    """Test serialization of Param nodes (now standard tasks)."""
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert param_node["input_bindings"]["name"] == "env"
    assert param_node["input_bindings"]["default"] == "dev"

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert p_node.input_bindings["name"] == "env"
    assert p_node.input_bindings["default"] == "dev"


def test_serialize_with_retry():
    """Test serialization of retry policy including backoff."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")

    assert task_node["retry_policy"]["max_attempts"] == 5
    assert task_node["retry_policy"]["delay"] == 1.0
    assert task_node["retry_policy"]["backoff"] == 2.0

    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")
    assert t_node.retry_policy.max_attempts == 5
    assert t_node.retry_policy.backoff == 2.0


def test_serialize_with_constraints():
    """Test serialization of resource constraints."""
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")

    assert "constraints" in task_node
    assert task_node["constraints"]["gpu_count"] == 1
    assert task_node["constraints"]["memory_gb"] == 16

    # Round trip
    restored = from_json(to_json(graph))
    t_node = next(n for n in restored.nodes if n.name == "simple_task")

    assert t_node.constraints is not None
    assert t_node.constraints.requirements["gpu_count"] == 1
    assert t_node.constraints.requirements["memory_gb"] == 16


def test_serialize_edge_types():
    """Test serialization and deserialization of various EdgeType instances."""

    # 1. Condition edge
    target_condition = t_target(t_dynamic_constraint(1)).run_if(t_condition())

    # 2. Constraint edge (dynamic)
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))

    graph, _, _ = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)

    # We only need to check the edges pointing to t_target (the target node of the chains)
    target_node = next(n for n in restored_graph.nodes if n.name == "t_target")

    data_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.DATA
    ]
    condition_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONDITION
    ]
    constraint_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONSTRAINT
    ]

    assert len(data_edges) == 1
    assert len(condition_edges) == 1
    assert len(constraint_edges) == 1

    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT


# --- Router Test Tasks ---
@cs.task
def get_route():
    return "a"


@cs.task
def task_a():
    return "A"


@cs.task
def task_b():
    return "B"


@cs.task
def consumer(val):
    return val


def test_serialize_router():
    """Test full round-trip serialization of a Router."""

    # Construct a router using top-level tasks
    selector = get_route()
    route_a = task_a()
    route_b = task_b()

    router = cs.Router(selector=selector, routes={"a": route_a, "b": route_b})

    # Consumer depends on the router
    target = consumer(router)

    # Build and Serialize
    graph, _, _ = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
    restored_graph = from_json(json_str)

    # Verify
    # Find the edge from selector to consumer (which carries the Router metadata)
    selector_node = next(n for n in restored_graph.nodes if n.name == "get_route")
    consumer_node = next(n for n in restored_graph.nodes if n.name == "consumer")

    # The edge between them should have the router attached
    edge = next(
        e
        for e in restored_graph.edges
        if e.source == selector_node and e.target == consumer_node
    )

    assert edge.router is not None
    # Check that the stub has the correct UUIDs
    assert edge.router.selector._uuid == selector._uuid
    assert edge.router.routes["a"]._uuid == route_a._uuid
    assert edge.router.routes["b"]._uuid == route_b._uuid
