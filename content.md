## [WIP] fix(core): 适配 ResourceContainer 和 Serializer 到新数据模型

### 用户需求
修复大量因 `Node` 模型变更（移除 `literal_inputs`）和 `build_graph` 返回值变更（返回 `(Graph, DataTuple)`）导致的 `AttributeError`。优先修复核心库代码，暂不修改测试代码。

### 评论
当前的错误主要源于两个组件尚未适配新模型：
1.  `ResourceContainer`：它负责扫描图以发现资源依赖 (`Inject`)。旧逻辑遍历 `literal_inputs`，但在新模型中，`Inject` 对象可能存在于 `DataTuple` 中。因此，`scan` 方法必须升级以同时检查 Graph（签名中的默认值）和 DataTuple（运行时参数）。
2.  `Serializer`：`graph_to_dict` 仍然尝试访问已删除的 `literal_inputs` 属性。我们需要更新它以序列化新的 `input_bindings`。

### 目标
1.  修改 `ResourceContainer.scan` 方法签名，使其接受 `data_tuple`。
2.  更新 `GraphExecutionStrategy` 以在调用 `scan` 时传递数据。
3.  更新 `cascade-graph/serialize.py` 以适配 `Node` 的新属性。

### 基本原理
资源注入 (`Inject`) 是 Cascade 的核心特性。在新架构中，`Inject` 对象作为参数传递时，会被 `GraphBuilder` 提取到 `DataTuple` 中。因此，资源扫描器必须遍历这个元组才能发现动态注入的需求。对于 `Serializer`，我们暂时将 `input_bindings` 序列化，以保持结构完整性。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/graph #concept/resource-injection #scope/core #ai/instruct #task/domain/core #task/object/resource-container #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 ResourceContainer

我们需要修改 `scan` 方法，使其接受 `data_tuple` 并从中提取资源依赖。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python
import inspect
from contextlib import ExitStack
from typing import Any, Dict, Callable, Union, Generator, Set, Tuple

from cascade.graph.model import Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import ResourceAcquired, ResourceReleased


class ResourceContainer:
    """
    Manages the lifecycle, registration, and dependency injection of resources.
    """

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

    def register(self, resource_def: ResourceDefinition):
        """Registers a resource definition."""
        self._resource_providers[resource_def.name] = resource_def

    def get_provider(self, name: str) -> Callable:
        """Retrieves the raw provider function for a resource."""
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_provider(self, name: str, new_provider: Any):
        """Overrides a resource provider (useful for testing)."""
        self._resource_providers[name] = new_provider

    def scan(self, graph: Graph, data_tuple: Tuple[Any, ...]) -> Set[str]:
        """
        Scans the graph and data tuple to identify all resources required by the nodes.
        """
        required = set()
        
        # 1. Scan DataTuple for explicit Inject objects passed as arguments
        for item in data_tuple:
            self._scan_item(item, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                try:
                    sig = inspect.signature(node.callable_obj)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required

    def _scan_item(self, item: Any, required: Set[str]):
        """Recursively scans an item for Inject objects."""
        if isinstance(item, Inject):
            required.add(item.resource_name)
        elif isinstance(item, (list, tuple)):
            for sub in item:
                self._scan_item(sub, required)
        elif isinstance(item, dict):
            for sub in item.values():
                self._scan_item(sub, required)

    def setup(
        self,
        required_names: Set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        """
        Initializes required resources that are not yet active.
        """

        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]

            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func

            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate
            gen = func(**deps)
            instance = next(gen)

            # Register in active dict
            active_resources[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register teardown in appropriate stack
            target_stack = step_stack if scope == "task" else run_stack

            def cleanup():
                self._teardown_resource(gen, run_id, name)
                # Important: remove from active_resources so it can be re-created if needed later
                active_resources.pop(name, None)

            target_stack.callback(cleanup)
            return instance

        for name in required_names:
            get_or_create(name)

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )
~~~~~

#### Acts 2: 更新 GraphExecutionStrategy

在 `strategies.py` 中，调用 `resource_container.scan` 时传入 `data_tuple`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
~~~~~
~~~~~python
                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
~~~~~

#### Acts 3: 适配 Serializer

修改 `serialize.py` 以适应 `Node` 模型的变更。注意，完整的序列化/反序列化（包括 DataTuple）需要更复杂的协议更新，这里我们先进行最小修复，即处理 `input_bindings` 替代 `literal_inputs`，防止 `AttributeError`。对于 DataTuple 的序列化，我们暂时不做（它主要影响跨进程传输，而当前的 E2E 测试主要在单进程内运行，或者不依赖全量序列化）。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
import json
import importlib
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from .model import Graph, Node, Edge, EdgeType
from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef, Constant


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
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        # Serializing bindings instead of literal_inputs
        "input_bindings": _serialize_bindings(node.input_bindings),
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


def _serialize_bindings(bindings: Dict[str, Any]) -> Dict[str, Any]:
    """Serializes the input_bindings dictionary."""
    serialized = {}
    for k, v in bindings.items():
        if isinstance(v, SlotRef):
            serialized[k] = {"__slot_ref": v.index}
        elif isinstance(v, Constant):
            serialized[k] = {"__constant": v.value} # Assuming value is JSON serializable
        else:
            # Fallback
            serialized[k] = v
    return serialized


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
        restored_routers.append(Router(selector=selector_stub, routes=routes_stubs))  # type: ignore

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
                edge_type=edge_type,
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
    
    # Recover Bindings
    input_bindings = _deserialize_bindings(data.get("input_bindings", {}))

    node = Node(
        id=data["id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        constraints=constraints,
        input_bindings=input_bindings, # Use reconstructed bindings
    )
    return node

def _deserialize_bindings(data: Dict[str, Any]) -> Dict[str, Any]:
    deserialized = {}
    for k, v in data.items():
        if isinstance(v, dict) and "__slot_ref" in v:
            deserialized[k] = SlotRef(index=v["__slot_ref"])
        elif isinstance(v, dict) and "__constant" in v:
            deserialized[k] = Constant(value=v["__constant"])
        else:
            deserialized[k] = v
    return deserialized


# --- Main API ---


def to_json(graph: Graph, indent: int = 2) -> str:
    """Serializes a Graph to a JSON string."""
    return json.dumps(graph_to_dict(graph), indent=indent)


def from_json(json_str: str) -> Graph:
    """Deserializes a Graph from a JSON string."""
    return graph_from_dict(json.loads(json_str))
~~~~~

### 下一步建议
通过这些修复，所有因为 `AttributeError: 'Node' object has no attribute 'literal_inputs'` 导致的测试失败应该会消失。那些因为调用者错误地将 `(Graph, Data)` 元组视为 `Graph` 而导致的 `AttributeError: 'tuple' object has no attribute 'nodes'` 仍然存在于测试文件中，但那需要更新测试代码（这不在此任务范围内，或者作为后续任务）。

接下来的重点是：
1.  验证 `tests/engine/runtime/test_engine_core.py`（该测试使用 `Engine.run`，应该能通过了）。
2.  确认 `test_resource_scheduling.py` 能通过（验证资源注入在新模型下正常工作）。
