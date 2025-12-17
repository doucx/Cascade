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