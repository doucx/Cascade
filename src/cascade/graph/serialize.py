import json
import importlib
from typing import Any, Dict, Optional
from .model import Graph, Node, Edge
from ..spec.common import Param
from ..spec.constraint import ResourceConstraint
from ..spec.routing import Router
from ..spec.lazy_types import RetryPolicy # NEW
from ..spec.task import Task

# --- Serialization Helpers ---

def _get_func_path(func: Any) -> Optional[Dict[str, str]]:
    """Extracts module and qualname from a callable."""
    if func is None:
        return None
    
    # If it's a Task instance, serialize the underlying function
    if isinstance(func, Task):
        func = func.func

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
        
        # If the object is a Task wrapper (due to @task decorator), unwrap it
        if isinstance(obj, Task):
            return obj.func
            
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

    if node.constraints:
        data["constraints"] = node.constraints.requirements

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