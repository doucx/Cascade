我理解了 `patch_file` 参数缺失的问题。在 Acts 2 中，我没有提供 `old_string` 和 `new_string`，导致操作失败。

我现在将修复 `tests/graph/test_serialize.py` 的 `patch_file` 操作，使用一个精确的锚点来追加新的测试用例。

## [WIP] refactor(graph): 实现 Router 对象的完整序列化与反序列化

### 用户需求
`src/cascade/graph/serialize.py` 目前无法正确序列化 `Router` 对象，导致在反序列化后丢失动态路由信息。需要修复此技术债务，确保存储在 `Graph` 中的 `Router` 元数据能够被无损地保存和恢复。

### 评论
当前的序列化逻辑只保存了一个 `router_present` 标志，这对于运行时恢复是完全不够的。
我们需要一种机制来序列化 `Router` 内部的结构（selector 和 routes），并在反序列化时重建它。由于 `Router` 引用的是 `LazyResult`（通常在 spec 阶段存在），而在反序列化 `Graph` 时我们只有 `Node` ID，因此我们需要引入一个轻量级的 `Stub` 对象来持有 ID，以满足 `ArgumentResolver` 在运行时的需求（它只通过 `_uuid` 属性来查找节点）。

### 目标
1.  重构 `src/cascade/graph/serialize.py`，增加对 `Router` 对象的完整支持。
2.  在序列化输出中增加 `routers` 顶级字段，存储去重后的 Router 定义。
3.  在反序列化时，使用 `_StubLazyResult` 重建 `Router` 实例，并将其正确链接到对应的 `Edge` 上。
4.  添加单元测试验证包含 `Router` 的图的 Round-Trip 序列化能力。

### 基本原理
通过将 `Router` 对象从 `Edge` 中提取出来单独序列化（类似于数据库中的规范化），我们可以解决多个边共享同一个 `Router` 实例的问题。使用 `_StubLazyResult` (仅包含 `_uuid` 的 dataclass) 来填充恢复后的 `Router` 对象，巧妙地解决了反序列化时缺乏完整 `LazyResult` 上下文的问题，同时满足了运行时组件对接口的最小依赖（Duck Typing）。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #concept/state #scope/core #ai/instruct #task/domain/core #task/object/serialization #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构序列化模块

我们将重写 `serialize.py`。
主要变更点：
1.  引入 `_StubLazyResult` 类。
2.  `graph_to_dict`：增加遍历 Edge 收集 Router 的逻辑，生成 `routers` 列表。
3.  `_edge_to_dict`：替换 `router_present` 标志为 `router_index`。
4.  `graph_from_dict`：先解析 `routers` 列表，重建 Router 对象池，再在解析 Edge 时进行链接。

~~~~~act
write_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
import json
import importlib
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from .model import Graph, Node, Edge, EdgeType
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from ..spec.routing import Router
from ..spec.task import Task


# --- Helpers ---


@dataclass
class _StubLazyResult:
    """
    A minimal stub to satisfy Router's type hints and runtime requirements 
    (specifically accessing ._uuid) during deserialization.
    """
    _uuid: str


def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    """Extracts module and qualname from a callable."""
    if func is None:
        return None

    # If it's a Task instance, serialize the underlying function
    if isinstance(func, Task):
        func = func.func

    # Handle wrapped functions or partials if necessary in future
    return {"module": func.__module__, "qualname": func.__qualname__}


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
        for part in qualname.split("."):
            obj = getattr(obj, part)

        # If the object is a Task wrapper (due to @task decorator), unwrap it
        if isinstance(obj, Task):
            return obj.func

        return obj
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Could not restore function {module_name}.{qualname}: {e}")


# --- Graph to Dict ---


def graph_to_dict(graph: Graph) -> Dict[str, Any]:
    # 1. Collect and Deduplicate Routers
    # Map id(router_obj) -> index_in_list
    router_map: Dict[int, int] = {}
    routers_data: List[Dict[str, Any]] = []

    for edge in graph.edges:
        if edge.router and id(edge.router) not in router_map:
            idx = len(routers_data)
            router_map[id(edge.router)] = idx
            
            # Serialize the Router object
            # We only need the UUIDs of the selector and routes to reconstruct dependencies
            routers_data.append({
                "selector_id": edge.router.selector._uuid,
                "routes": {k: v._uuid for k, v in edge.router.routes.items()}
            })

    # 2. Serialize Nodes
    nodes_data = [_node_to_dict(n) for n in graph.nodes]

    # 3. Serialize Edges (referencing routers by index)
    edges_data = [_edge_to_dict(e, router_map) for e in graph.edges]

    return {
        "nodes": nodes_data,
        "edges": edges_data,
        "routers": routers_data,
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
            "type_name": node.param_spec.type.__name__
            if node.param_spec.type
            else None,
            "description": node.param_spec.description,
        }

    if node.retry_policy:
        data["retry_policy"] = {
            "max_attempts": node.retry_policy.max_attempts,
            "delay": node.retry_policy.delay,
            "backoff": node.retry_policy.backoff,
        }

    if node.constraints:
        # Dynamic constraints contain LazyResult/MappedLazyResult which are not JSON serializable.
        # We must replace them with their UUID reference.
        serialized_reqs = {}
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                # Store the UUID reference as a JSON serializable dict.
                serialized_reqs[res] = {"__lazy_ref": amount._uuid}
            else:
                serialized_reqs[res] = amount
        data["constraints"] = serialized_reqs

    return data


def _edge_to_dict(edge: Edge, router_map: Dict[int, int]) -> Dict[str, Any]:
    data = {
        "source_id": edge.source.id,
        "target_id": edge.target.id,
        "arg_name": edge.arg_name,
        "edge_type": edge.edge_type.name,
    }
    if edge.router:
        # Store the index to the routers list
        if id(edge.router) in router_map:
            data["router_index"] = router_map[id(edge.router)]
    return data


# --- Dict to Graph ---


def graph_from_dict(data: Dict[str, Any]) -> Graph:
    nodes_data = data.get("nodes", [])
    edges_data = data.get("edges", [])
    routers_data = data.get("routers", [])

    node_map: Dict[str, Node] = {}
    graph = Graph()

    # 1. Reconstruct Nodes
    for nd in nodes_data:
        node = _dict_to_node(nd)
        node_map[node.id] = node
        graph.add_node(node)

    # 2. Reconstruct Routers
    # We create Router objects populated with _StubLazyResult
    restored_routers: List[Router] = []
    for rd in routers_data:
        selector_stub = _StubLazyResult(rd["selector_id"])
        routes_stubs = {k: _StubLazyResult(uuid) for k, uuid in rd["routes"].items()}
        # Note: Type checker might complain because we are passing Stubs instead of LazyResults,
        # but Python is duck-typed and this satisfies the runtime needs.
        restored_routers.append(Router(selector=selector_stub, routes=routes_stubs)) # type: ignore

    # 3. Reconstruct Edges
    for ed in edges_data:
        source = node_map.get(ed["source_id"])
        target = node_map.get(ed["target_id"])
        if source and target:
            edge_type_name = ed.get("edge_type", "DATA")
            edge_type = EdgeType[edge_type_name]
            
            edge = Edge(
                source=source, 
                target=target, 
                arg_name=ed["arg_name"], 
                edge_type=edge_type
            )
            
            # Re-attach Router object if present
            if "router_index" in ed:
                r_idx = ed["router_index"]
                if 0 <= r_idx < len(restored_routers):
                    edge.router = restored_routers[r_idx]

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
            description=ps_data["description"],
        )

    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"], delay=rp["delay"], backoff=rp["backoff"]
        )

    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])

    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        constraints=constraints,
        literal_inputs=data.get("literal_inputs", {}),
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

#### Acts 2: 添加测试用例

在 `tests/graph/test_serialize.py` 中添加一个新的测试函数，验证包含 `Router` 的图的 Round-Trip 序列化能力。

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT
~~~~~
~~~~~python
    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT


def test_serialize_router():
    """Test full round-trip serialization of a Router."""
    
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
        
    # Construct a router
    selector = get_route()
    route_a = task_a()
    route_b = task_b()
    
    router = cs.Router(
        selector=selector,
        routes={"a": route_a, "b": route_b}
    )
    
    # Consumer depends on the router
    target = consumer(router)
    
    # Build and Serialize
    graph = build_graph(target)
    json_str = to_json(graph)
    
    # Deserialize
    restored_graph = from_json(json_str)
    
    # Verify
    # Find the edge from selector to consumer (which carries the Router metadata)
    # The selector node name is "get_route"
    # The consumer node name is "consumer"
    
    selector_node = next(n for n in restored_graph.nodes if n.name == "get_route")
    consumer_node = next(n for n in restored_graph.nodes if n.name == "consumer")
    
    # The edge between them should have the router attached
    edge = next(e for e in restored_graph.edges if e.source == selector_node and e.target == consumer_node)
    
    assert edge.router is not None
    # Check that the stub has the correct UUIDs
    assert edge.router.selector._uuid == selector._uuid
    assert edge.router.routes["a"]._uuid == route_a._uuid
    assert edge.router.routes["b"]._uuid == route_b._uuid
~~~~~

### 下一步建议
序列化问题解决后，我们已经为分布式执行打下了基础。
接下来的重点应转向 **DX (开发者体验)** 的提升。建议开始规划和实施 **标准库 Provider** 的扩展，特别是 `cs.template` 的强化，使其成为独立的、可序列化的节点，进一步解耦业务逻辑。
