import json
import importlib
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from .model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task


# --- Helpers ---


@dataclass
class _StubLazyResult:
    _uuid: str


def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    if func is None:
        return None

    # If it's a Task instance, serialize the underlying function
    if isinstance(func, Task):
        func = func.func

    # Handle wrapped functions or partials if necessary in future
    return {"module": func.__module__, "qualname": func.__qualname__}


def _load_func_from_path(data: Optional[Dict[str, str]]) -> Optional[Any]:
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
            routers_data.append(
                {
                    "selector_id": edge.router.selector._uuid,
                    "routes": {k: v._uuid for k, v in edge.router.routes.items()},
                }
            )

    # 2. Serialize Nodes
    nodes_data = [_node_to_dict(n) for n in graph.nodes]

    # 3. Serialize Edges (referencing routers by index)
    edges_data = [_edge_to_dict(e, router_map) for e in graph.edges]

    return {
        "nodes": nodes_data,
        "edges": edges_data,
        "routers": routers_data,
        # TODO: Add data_tuple serialization support
    }


def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "current_node_instance_hash": node.current_node_instance_hash,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    if isinstance(node, TaskNode):
        if node.callable_obj:
            data["callable"] = _get_func_path(node.callable_obj)
    elif isinstance(node, MapNode):
        if node.mapping_factory:
            data["mapping_factory"] = _get_func_path(node.mapping_factory)
    elif isinstance(node, ParamNode):
        # We don't serialize the spec for now, but could in the future
        pass

    # Note: param_spec serialization removed as Node no longer holds it directly.
    # Future implementation should serialize definition metadata if needed.

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
        "source_node_instance_hash": edge.source.current_node_instance_hash,
        "target_node_instance_hash": edge.target.current_node_instance_hash,
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
        node_map[node.current_node_instance_hash] = node
        graph.add_node(node)

    # 2. Reconstruct Routers
    # We create Router objects populated with _StubLazyResult
    restored_routers: List[Router] = []
    for rd in routers_data:
        selector_stub = _StubLazyResult(rd["selector_id"])
        routes_stubs = {k: _StubLazyResult(uuid) for k, uuid in rd["routes"].items()}
        # Note: Type checker might complain because we are passing Stubs instead of LazyResults,
        # but Python is duck-typed and this satisfies the runtime needs.
        restored_routers.append(Router(selector=selector_stub, routes=routes_stubs))  # type: ignore

    # 3. Reconstruct Edges
    for ed in edges_data:
        source = node_map.get(ed["source_node_instance_hash"])
        target = node_map.get(ed["target_node_instance_hash"])
        if source and target:
            edge_type_name = ed.get("edge_type", "DATA")
            edge_type = EdgeType[edge_type_name]

            edge = Edge(
                source=source,
                target=target,
                arg_name=ed["arg_name"],
                edge_type=edge_type,
            )

            # Re-attach Router object if present
            if "router_index" in ed:
                r_idx = int(ed["router_index"])
                if 0 <= r_idx < len(restored_routers):
                    edge.router = restored_routers[r_idx]

            graph.add_edge(edge)
        else:
            raise ValueError(f"Edge references unknown node: {ed}")

    return graph


def _dict_to_node(data: Dict[str, Any]) -> Node:
    # Note: param_spec recovery removed

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

    # Reconstruct a minimal TaskDef for the Node from the serialized data
    # This is a stub definition to satisfy the Node contract for deserialization
    from cascade.spec.ir.models import TaskDef
    from cascade.spec.fingerprint import Fingerprint

    # We use a dummy fingerprint for deserialized nodes if not present
    fp = Fingerprint()
    # If we serialized the code hash, we should restore it, but for now we put a placeholder
    fp["current_code_structure_hash"] = "restored_from_json"

    stub_def = TaskDef(
        name=data["name"],
        args=[],  # Args info lost in simplified serialization, ok for basic runtime restoration if callables are loaded
        fingerprint=fp,
    )

    node_type = data["node_type"]
    input_bindings = data.get("input_bindings", {})
    
    if node_type == "map":
        node = MapNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="map",
            mapping_factory=_load_func_from_path(data.get("mapping_factory")),
            retry_policy=retry_policy,
            cache_policy=None, # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="param",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
        node = TaskNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="task",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            # has_complex_inputs is an optimization flag, safe to default False on restore
            has_complex_inputs=False, 
        )
    return node


# --- Main API ---


def to_json(graph: Graph, indent: int = 2) -> str:
    return json.dumps(graph_to_dict(graph), indent=indent)


def from_json(json_str: str) -> Graph:
    return graph_from_dict(json.loads(json_str))