简要回答：
实现图与任务的序列化是构建分布式执行和可视化编辑器的基石。我将创建一个新的 `serialize` 模块，利用 Python 的内省机制处理函数引用的序列化，并实现 `Graph` 对象的 JSON 导入/导出功能。

## [WIP] feat(core): 实现计算图与任务的 JSON 序列化

### 用户需求
实现将内存中的计算图（`Graph`）及其组件（`Node`, `Edge`）序列化为通用 JSON 格式的能力，并支持从 JSON 反序列化回内存对象。这需要处理 Python 函数对象的引用持久化问题。

### 评论
这是一个关键的基础设施层变更。虽然 JSON 不是传输可执行代码（Pickle 更合适）的标准格式，但它对于元数据交换、UI 前端集成和跨语言互操作性至关重要。难点在于如何优雅地处理 Python `callable` 的序列化与恢复，我们将采用 "Import Path" 策略（存储模块路径和函数名）来解决这个问题。

### 目标
1.  创建 `src/cascade/graph/serialize.py` 模块。
2.  实现 `to_json(graph: Graph) -> str` 和 `from_json(json_str: str) -> Graph`。
3.  确保序列化机制能正确处理 `Task`（函数引用）、`Param`、`Map` 和 `Edge` 结构。
4.  添加完整的单元测试，验证序列化->反序列化的无损性（Round-trip correctness）。

### 基本原理
我们将定义一个标准的 JSON Schema 来描述图结构。对于 `Node` 中的 `callable_obj`，我们将提取其 `__module__` 和 `__qualname__` 进行存储；在反序列化时，使用 `importlib` 动态加载这些函数。这将允许我们在不同的进程甚至机器上（假设代码环境一致）重建执行图。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/state #task/domain/core #task/object/serialization #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建序列化模块

我们需要一个新的模块来封装序列化逻辑，保持核心模型的纯净。

~~~~~act
write_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
import json
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.routing import Router
from ..spec.task import RetryPolicy

# --- Serialization Helpers ---

def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    """Extracts module and qualname from a callable."""
    if func is None:
        return None
    # Handle wrapped functions or partials if necessary in future
    return {
        "module": func.__module__,
        "qualname": func.__qualname__
    }

def _load_func_from_path(data: Optional[Dict[str, str]]) -> Optional[Any]:
    """Dynamically loads a function from module and qualname."""
    if not data:
        return None
    module_name = data.get("module")
    qualname = data.get("qualname")
    
    if not module_name or not qualname:
        return None

    try:
        module = importlib.import_module(module_name)
        # Handle nested classes/functions (e.g. MyClass.method)
        obj = module
        for part in qualname.split('.'):
            obj = getattr(obj, part)
        return obj
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Could not restore function {module_name}.{qualname}: {e}")

# --- Graph to Dict ---

def graph_to_dict(graph: Graph) -> Dict[str, Any]:
    return {
        "nodes": [_node_to_dict(n) for n in graph.nodes],
        "edges": [_edge_to_dict(e) for e in graph.edges],
    }

def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "literal_inputs": node.literal_inputs,  # Assumes JSON-serializable literals
    }

    if node.callable_obj:
        data["callable"] = _get_func_path(node.callable_obj)
    
    if node.mapping_factory:
        data["mapping_factory"] = _get_func_path(node.mapping_factory)

    if node.param_spec:
        data["param_spec"] = {
            "name": node.param_spec.name,
            "default": node.param_spec.default,
            "type_name": node.param_spec.type.__name__ if node.param_spec.type else None,
            "description": node.param_spec.description
        }
    
    if node.retry_policy:
        # Assuming RetryPolicy is a simple dataclass-like object we can reconstruct
        # But RetryPolicy in task.py is a class. We should serialize its fields.
        data["retry_policy"] = {
            "max_attempts": node.retry_policy.max_attempts,
            "delay": node.retry_policy.delay,
            "backoff": node.retry_policy.backoff
        }

    return data

def _edge_to_dict(edge: Edge) -> Dict[str, Any]:
    data = {
        "source_id": edge.source.id,
        "target_id": edge.target.id,
        "arg_name": edge.arg_name,
    }
    if edge.router:
        # Router is complex, but for the edge we just need to mark it or verify consistency
        # In current model, router object is attached to edge.
        # We need to serialize enough info to reconstruct the Router logic if needed,
        # but the Router spec object itself is mostly build-time. 
        # Runtime logic depends on the edge structure.
        # For now, we simply flag it.
        data["router_present"] = True
    return data

# --- Dict to Graph ---

def graph_from_dict(data: Dict[str, Any]) -> Graph:
    nodes_data = data.get("nodes", [])
    edges_data = data.get("edges", [])

    node_map: Dict[str, Node] = {}
    graph = Graph()

    # 1. Reconstruct Nodes
    for nd in nodes_data:
        node = _dict_to_node(nd)
        node_map[node.id] = node
        graph.add_node(node)

    # 2. Reconstruct Edges
    for ed in edges_data:
        source = node_map.get(ed["source_id"])
        target = node_map.get(ed["target_id"])
        if source and target:
            # Note: We are losing the original 'Router' spec object here.
            # If runtime requires the Router object on the edge, we might need to rethink.
            # Checking `LocalExecutor`: it checks `edge.router`. 
            # If `edge.router` is None, dynamic routing fails.
            # So we MUST reconstruct a Router object if `router_present` is True.
            
            # However, the `Router` object in spec needs `routes` dict and `selector` LazyResult.
            # Reconstructing that from a flat edge list is hard.
            # BUT, look at `LocalExecutor`: it uses `edge.router.routes` to find the implementation node.
            # This implies the graph structure already contains the routes.
            # The Executor uses `edge.router` mainly as a marker and a lookup table for `routes`.
            
            # For this MVP, we will revive the Edge. 
            # TODO: Fully restoring Router object requires matching the "implicit_dependency" edges 
            # back to the routes dict. This is complex. 
            # For basic serialization (visualization/inspection), omitting Router object is fine.
            # For Distributed Execution, we will need full reconstruction.
            # Let's leave a TODO for Router reconstruction and support basic edges.
            
            edge = Edge(
                source=source,
                target=target,
                arg_name=ed["arg_name"]
            )
            # If we marked it as having a router, we might want to attach a placeholder or
            # address this in a future PR for distributed routing.
            graph.add_edge(edge)
        else:
            raise ValueError(f"Edge references unknown node: {ed}")

    return graph

def _dict_to_node(data: Dict[str, Any]) -> Node:
    # Recover Param Spec
    param_spec = None
    if "param_spec" in data:
        ps_data = data["param_spec"]
        # Recovering type is hard without `pydoc.locate` or similar, defaulting to None or str
        param_spec = Param(
            name=ps_data["name"],
            default=ps_data["default"],
            description=ps_data["description"]
        )

    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"],
            delay=rp["delay"],
            backoff=rp["backoff"]
        )

    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        literal_inputs=data.get("literal_inputs", {})
    )
    return node

# --- Main API ---

def to_json(graph: Graph, indent: int = 2) -> str:
    """Serializes a Graph to a JSON string."""
    return json.dumps(graph_to_dict(graph), indent=indent)

def from_json(json_str: str) -> Graph:
    """Deserializes a Graph from a JSON string."""
    return graph_from_dict(json.loads(json_str))
~~~~~

#### Acts 2: 暴露 API

更新 `__init__.py` 使新功能可用。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~
~~~~~python
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "to_json",
    "from_json",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~

#### Acts 3: 添加测试用例

编写测试以验证序列化和反序列化的正确性，特别是函数引用的恢复。

~~~~~act
write_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
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
    assert node_simple["callable"]["qualname"] == "test_serialize_basic_graph.<locals>.simple_task"
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
    assert restored_node.callable_obj == simple_task
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
~~~~~

### 下一步建议
我们现在拥有了 `Graph` 对象的序列化能力。
这开启了两个可能性：
1.  **持久化/缓存编译后的图**：对于大型图，可以避免重复 build 开销。
2.  **Web UI 编辑器**：可以将 JSON 发送给前端进行渲染。

鉴于 `cs.Router` 的反序列化支持目前还是有限的（丢失了 `Router` 对象本身，只保留了边），如果我们要支持完全的分布式执行，将来需要增强这一点。

当前的序列化功能已经足够支持 **“可视化导出”** 这一高频需求。下一个逻辑步骤可能是利用这个能力，或者继续推进 **Task Map** 功能。根据之前的路线图，我们应优先完成 **任务映射 (`.map`)**。
