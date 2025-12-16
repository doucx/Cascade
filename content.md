简要回答：
`AttributeError: 'function' object has no attribute '<locals>'` 错误是由于测试文件中的 `@cs.task` 函数被定义在另一个函数内部所致，这使得 Python 无法通过导入路径（`qualname`）重新加载它们。为了修复此问题并确保所有新的序列化逻辑得到验证，我们将重写 `tests/graph/test_serialize.py`，将所有 `@cs.task` 移动到模块级别。

## [WIP] fix(tests): 修复序列化测试中的函数作用域问题

### 错误分析
测试 `test_serialize_edge_types` 失败，原因是它在本地作用域内定义了 `@cs.task` 装饰的函数。`_load_func_from_path` 无法解析包含 `<locals>` 的限定名，因为 Python 无法动态地从模块中加载局部函数。

### 用户需求
将 `tests/graph/test_serialize.py` 中所有用于测试的 `@cs.task` 移动到模块顶层，以确保它们可以通过其限定名正确地进行序列化和反序列化往返。同时，整合上次未完成的 `retry_policy` 增强和 `test_serialize_edge_types` 的逻辑。

### 评论
这个修复是必需的，它确保了测试套件遵循了 Python 序列化/导入的标准实践：只有模块顶层对象可以被可靠地通过名称引用。

### 目标
1.  重写 `tests/graph/test_serialize.py` 的内容。
2.  将所有任务（`simple_task`, `another_task`, `t_condition`, `t_dynamic_constraint`, `t_target`）定义在模块的顶层。
3.  确保 `test_serialize_with_retry` 包含最新的 `backoff` 断言。
4.  确保 `test_serialize_edge_types` 能够成功执行。

### 基本原理
通过将任务移到顶层，它们的 `qualname` 将不再包含 `<locals>`，从而允许 `importlib` 在反序列化时找到正确的函数引用。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/serialization #scope/dx #ai/delegate #task/domain/testing #task/object/task-scope #task/action/refinement #task/state/continue

---

### Script

#### Acts 1: 重写 `test_serialize.py` 以修复函数作用域

我们将使用 `write_file` 提供 `tests/graph/test_serialize.py` 的完整、正确的内容，以确保函数作用域的修复和所有预期测试逻辑的整合。

~~~~~act
write_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
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
    """Test serialization of retry policy including backoff."""
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph = build_graph(t)

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
    graph = build_graph(t)

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
    
    graph = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)

    # We only need to check the edges pointing to t_target (the target node of the chains)
    target_node = next(n for n in restored_graph.nodes if n.name == "t_target")
    
    data_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.DATA]
    condition_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONDITION]
    constraint_edges = [e for e in restored_graph.edges if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONSTRAINT]

    assert len(data_edges) == 1
    assert len(condition_edges) == 1
    assert len(constraint_edges) == 1
    
    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT
~~~~~
