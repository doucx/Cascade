好的，我理解了当前的断裂状态和修复路线图。这是一个典型的在大型重构中出现的“中间态”问题，需要对系统的多个层面进行对齐，以恢复一致性。你的路线图非常清晰，我将严格按照此计划执行。

我将生成一个计划，其中包含一系列 `patch_file` 和 `write_file` 操作，以完成 Node 多态化重构的收尾工作。

## [WIP] fix: 完成 Node 多态化重构并对齐系统各层

### 错误分析
系统当前处于一个不稳定的中间状态。核心 `Node` 模型的重构（拆分为 `TaskNode`, `MapNode`, `ParamNode`）未完全同步到系统的其他部分，导致了连锁故障：
1.  **接口不一致**: 部分新的 `Node` 子类缺少父类已有的属性（如 `has_complex_inputs`），导致依赖此接口的 `ArgumentResolver` 出现 `AttributeError`。
2.  **逻辑断裂**: `ParamNode` 因为错误的 `has_complex_inputs` 标志（`False`），被 `ArgumentResolver` 走了错误的“简单路径”，未能注入必要的 `params_context`，最终导致下游任务出现 `DependencyMissingError`。
3.  **序列化层崩溃**: `serialize.py` 未更新以识别新的节点类型，同时存在代码错误（如引用不存在的变量），导致其无法工作。
4.  **测试过时**: 测试用例仍在引用旧的 `Node` 构造函数和断言逻辑，无法正确验证新模型，产生了大量直接的 `TypeError` 和 `AssertionError`。

### 用户需求
核心目标是消除所有因本次重构引入的 `AttributeError`、`DependencyMissingError` 和 `NameError`，完成 Node 多态化，实现整个计算图生命周期的类型安全和功能正确。

### 评论
这是一个非常关键的修复计划。它解决了重构过程中的技术债，将一个不稳定的、半完成的特性推向稳定状态。完成此次对齐后，核心数据模型的表达将更加清晰和健壮，为后续的开发和维护打下坚实的基础。

### 目标
1.  **稳固模型**：为 `MapNode` 和 `ParamNode` 添加 `has_complex_inputs` 属性，统一接口。
2.  **修正构建逻辑**：在 `build.py` 中为 `ParamNode` 强制设置 `has_complex_inputs=True`，确保参数注入逻辑能被正确触发。
3.  **修复序列化**：重构 `serialize.py`，使其能够正确地序列化和反序列化多态的 `Node` 对象。
4.  **对齐测试**：更新所有受影响的测试用例，使其与新的 `Node` 模型（`TaskNode`）和断言逻辑（`node_type`）保持一致。

### 基本原理
我们将采用一系列精确的、原子化的补丁操作来逐一修复上述断点。
-   首先，从最底层的 `model.py` 开始，确保数据模型本身是一致和完整的。
-   其次，修复直接依赖模型的 `build.py` 和 `serialize.py`，恢复图的构建和持久化能力。
-   最后，更新上层的测试代码，使其能够正确地验证新模型的行为，从而将整个系统恢复到可测试、可验证的健康状态。

### 标签
#intent/fix #flow/ready #priority/high #comp/graph #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core-model #task/object/node-polymorphism #task/action/refactor-completion #task/state/continue

---
### Script

#### Acts 1: 稳固底层模型 (`model.py`)

首先，我们为 `MapNode` 和 `ParamNode` 添加缺失的 `has_complex_inputs` 属性，以确保所有 `Node` 子类都符合 `ArgumentResolver` 所期望的接口。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""
    
    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec
    param_spec: Optional[ParamSpec] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # Param nodes use a special internal task to retrieve values
        from cascade.internal.inputs import _get_param_value
        return _get_param_value.func
~~~~~
~~~~~python.new
@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""

    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec

    param_spec: Optional[ParamSpec] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        # Param nodes use a special internal task to retrieve values
        from cascade.internal.inputs import _get_param_value
        return _get_param_value.func
~~~~~

#### Acts 2: 修正图构建逻辑 (`build.py`)

接下来，我们修正 `build.py`。导入新的 Node 类型，并为 `ParamNode` 设置 `has_complex_inputs=True`，这是修复参数注入的关键。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec
                )
~~~~~
~~~~~python.new
                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
~~~~~

#### Acts 3: 修复序列化层 (`serialize.py`)

序列化模块的改动较大，涉及多处逻辑修正和类型导入。因此，我们使用 `write_file` 进行覆盖式更新，确保其内部逻辑的完整性和正确性。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
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
        "structural_id": node.structural_id,
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
        "source_id": edge.source.structural_id,
        "target_id": edge.target.structural_id,
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
        node_map[node.structural_id] = node
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
            structural_id=data["structural_id"],
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
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="param",
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
        node = TaskNode(
            structural_id=data["structural_id"],
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
~~~~~

#### Acts 4: 对齐执行器测试 (`test_local.py`)

现在，我们更新执行器测试，用 `TaskNode` 替换旧的 `Node` 实例化，并修正构造函数参数。

~~~~~act
patch_file
packages/cascade-engine/tests/adapters/executors/test_local.py
~~~~~
~~~~~python.old
import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node
from cascade.spec.task import task


from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint


def test_local_executor_sync_execution():
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = Node(structural_id="add", definition=stub_def, callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_add, resolved_args, resolved_kwargs))

    assert result == 17  # 5 + 10 + 2


def test_local_executor_async_execution():
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    # Must explicit set is_async=True for the executor to treat it as a coroutine
    stub_def = TaskDef(
        name="async_add", args=[], fingerprint=Fingerprint(), is_async=True
    )
    node_async = Node(
        structural_id="async_add", definition=stub_def, callable_obj=async_add.func
    )

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_async, resolved_args, resolved_kwargs))

    assert result == 6
~~~~~
~~~~~python.new
import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import TaskNode
from cascade.spec.task import task


from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint


def test_local_executor_sync_execution():
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = TaskNode(structural_id="add", definition=stub_def, _callable=add.func)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_add, resolved_args, resolved_kwargs))

    assert result == 17  # 5 + 10 + 2


def test_local_executor_async_execution():
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    # Must explicit set is_async=True for the executor to treat it as a coroutine
    stub_def = TaskDef(
        name="async_add", args=[], fingerprint=Fingerprint(), is_async=True
    )
    node_async = TaskNode(
        structural_id="async_add", definition=stub_def, _callable=async_add.func
    )

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_async, resolved_args, resolved_kwargs))

    assert result == 6
~~~~~

#### Acts 5: 更新测试断言 (`test_build.py` & `test_serialize.py`)

最后，我们更新图构建和序列化测试中的断言，使其反映 `ParamNode` 正确的 `node_type`。

~~~~~act
patch_file
packages/cascade-graph/tests/test_build.py
~~~~~
~~~~~python.old
    # 断言节点类型统一为 task
    assert p_node.node_type == "task"

    # 断言它包含正确的 input_bindings (这是内部任务需要的参数)
~~~~~
~~~~~python.new
    # The node type should now be correctly identified as 'param'
    assert p_node.node_type == "param"

    # 断言它包含正确的 input_bindings (这是内部任务需要的参数)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/test_serialize.py
~~~~~
~~~~~python.old
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
~~~~~
~~~~~python.new
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "param"
    assert "name" in param_node["input_bindings"]
~~~~~

### 下一步建议
我们已经根据路线图应用了所有必要的修复。现在，最关键的步骤是重新运行完整的测试套件，以验证这些改动是否已经解决了所有已识别的故障，并且没有引入新的回归问题。

我建议你立即执行 `pytest`，并检查输出，特别是 `test_input_execution.py` 和 `test_serialize.py` 的测试结果。如果所有测试通过，我将生成一个 `[COMMIT]` 计划来提交这些变更。
