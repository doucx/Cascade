好的，我们正式进入**阶段二：架构直觉化**。

这一阶段的核心目标是让 `Cascade` 的行为更符合 Python 开发者的直觉，消除那些“看起来应该能工作但实际上不行”的陷阱（如列表中的依赖），并提供更符合人体工程学的工具（如 `cs.dict`, `cs.format`）。

我们将一次性解决 `GraphBuilder` 的浅层扫描问题、`ArgumentResolver` 的解析策略、以及 `cs.inject` 的静默失败问题，并引入新的工具原子。

## [WIP] feat: 架构直觉化 - 深度图构建与人体工程学优化

### 错误分析
当前 `GraphBuilder` 仅遍历顶层参数来寻找 `LazyResult` 依赖，导致嵌套在列表或字典中的任务（如 `task([a(), b()])`）无法被正确识别为依赖，从而在运行时引发错误。
同时，`ArgumentResolver` 依赖于扁平的参数映射，无法还原复杂的嵌套结构。
此外，`cs.inject` 在资源缺失时缺乏明确报错，增加了调试难度。

### 用户需求
1.  **深度依赖支持**: 支持在列表、字典等容器内部嵌套使用 `LazyResult`，且能被正确构建进图并解析。
2.  **明确的 DI 报错**: 当 `cs.inject` 找不到资源时，抛出 `ResourceNotFoundError` 而非静默失败或注入 `None`。
3.  **人体工程学工具**:
    *   新增 `cs.format` (类似 `str.format`)。
    *   新增 `cs.dict` (用于组合字典)。

### 目标
1.  重构 `GraphBuilder` 以支持递归扫描参数中的 `LazyResult` 和 `Router`。
2.  重构 `ArgumentResolver` 以支持对 `literal_inputs` 的深度遍历和原地替换解析。
3.  更新 `serialize.py` 以支持序列化嵌套在 `literal_inputs` 中的 `LazyResult`。
4.  实现 `cs.dict` 和 `cs.format` 提供者。

### 基本原理
我们将改变图构建和参数解析的策略：
*   **构建时**: `GraphBuilder` 将完整的参数结构（包含 `LazyResult` 对象）保留在 `node.literal_inputs` 中，并递归扫描该结构以添加图的边（Edge）。
*   **运行时**: `ArgumentResolver` 不再尝试将 Edge 映射回参数位置，而是直接遍历 `node.literal_inputs` 结构，将遇到的 `LazyResult` 占位符替换为 `StateBackend` 中的实际结果。
*   这种“保留结构、原地替换”的策略天然支持任意深度的嵌套。

### 标签
#intent/refine #intent/build #flow/draft #priority/high
#comp/runtime #comp/py #concept/graph #concept/di
#task/domain/core #task/object/graph-builder #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 创建 `cs.dict` 和 `cs.format` 提供者

这两个工具非常简单，我们将它们放在一个新的 `helpers` 模块中。

~~~~~act
write_file
packages/cascade-py/src/cascade/providers/helpers.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


# --- Tasks ---

@task(name="dict")
def _dict_task(**kwargs) -> Dict[str, Any]:
    """
    Creates a dictionary from keyword arguments.
    Useful for composing dynamic contexts in the graph.
    """
    return kwargs


@task(name="format")
def _format_task(template: str, *args, **kwargs) -> str:
    """
    Formats a string using Python's str.format syntax.
    
    Usage:
        cs.format("Hello, {name}!", name=cs.Param("name"))
    """
    return template.format(*args, **kwargs)


# --- Providers ---

class DictProvider(Provider):
    name = "dict"

    def create_factory(self) -> LazyFactory:
        return _dict_task


class FormatProvider(Provider):
    name = "format"

    def create_factory(self) -> LazyFactory:
        return _format_task
~~~~~

#### Acts 2: 注册新 Provider

更新 `pyproject.toml` 以注册新的入口点。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
"io.stdin.read_line" = "cascade.providers.stdio:StdInReadLineProvider"
dict = "cascade.providers.helpers:DictProvider"
format = "cascade.providers.helpers:FormatProvider"

[tool.hatch.build.targets.wheel]
~~~~~

#### Acts 3: 定义新的异常类型

我们需要一个明确的异常来处理资源缺失。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/exceptions.py
~~~~~
~~~~~python
        super().__init__(
            f"Task '{task_id}' cannot execute: missing input for argument '{arg_name}'. "
            f"Dependency '{dependency_id}' did not produce a result (it may have been skipped)."
        )
~~~~~
~~~~~python
        super().__init__(
            f"Task '{task_id}' cannot execute: missing input for argument '{arg_name}'. "
            f"Dependency '{dependency_id}' did not produce a result (it may have been skipped)."
        )


class ResourceNotFoundError(CascadeRuntimeError):
    """Raised when a requested resource is not available in the context."""

    def __init__(self, resource_name: str, consumer_name: str = "unknown"):
        super().__init__(
            f"Resource '{resource_name}' required by '{consumer_name}' was not found. "
            "Ensure it is registered with the Engine or provided via system_resources."
        )
~~~~~

#### Acts 4: 重构 `GraphBuilder` 实现深度扫描

我们将重写 `GraphBuilder`，使其能递归地扫描参数结构，并将完整的结构（包含 `LazyResult`）保存在 `literal_inputs` 中。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, List, Union
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # 1. Capture the structure of inputs
        # We store the args/kwargs structure directly in literal_inputs.
        # This structure contains LazyResult objects, which is fine for the runtime,
        # but requires special handling for serialization.
        literal_inputs = {
            str(i): v for i, v in enumerate(result.args)
        }
        literal_inputs.update(result.kwargs)

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        # 3. Handle conditionals
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        # 4. Handle dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name,
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=result.mapping_kwargs, # Map inputs are treated as kwargs
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        """
        Recursively scans the object for LazyResults and Routers to add edges.
        """
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj)
            # We add a generic DATA edge. The exact argument position is determined
            # by ArgumentResolver traversing literal_inputs, so arg_name here is
            # mainly for visualization/debugging.
            edge = Edge(
                source=source_node,
                target=target_node,
                arg_name=path or "dependency",
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

        elif isinstance(obj, Router):
            # 1. Add edge for Selector
            selector_node = self._visit(obj.selector)
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=f"{path}.selector" if path else "selector",
                router=obj, # Important: Link Router to this edge for FlowManager
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

            # 2. Add edges for Routes
            for route_key, route_result in obj.routes.items():
                route_node = self._visit(route_result)
                imp_edge = Edge(
                    source=route_node,
                    target=target_node,
                    arg_name=f"{path}.route[{route_key}]",
                    edge_type=EdgeType.ROUTER_ROUTE,
                )
                self.graph.add_edge(imp_edge)

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))
        
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))


def build_graph(target: LazyResult) -> Graph:
    return GraphBuilder().build(target)
~~~~~

#### Acts 5: 重构 `ArgumentResolver` 实现深度解析

重写解析逻辑，使用递归遍历和原地替换。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.interfaces.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by traversing the structure stored in node.literal_inputs
    and replacing LazyResult/Router/Inject placeholders with actual values.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        # Special handling for internal param fetcher
        from cascade.internal.inputs import _get_param_value
        if node.callable_obj is _get_param_value.func:
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # Recursively resolve the structure
        resolved_structure = self._resolve_structure(
            node.literal_inputs, node.id, state_backend, resource_context
        )

        # Re-assemble args and kwargs
        final_kwargs = {k: v for k, v in resolved_structure.items() if not k.isdigit()}
        positional_args_dict = {
            int(k): v for k, v in resolved_structure.items() if k.isdigit()
        }
        
        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # Handle Inject in defaults (if not overridden by inputs)
        if node.callable_obj:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        return args, final_kwargs

    def _resolve_structure(
        self, obj: Any, consumer_id: str, state_backend: StateBackend, resource_context: Dict[str, Any]
    ) -> Any:
        """
        Recursively traverses lists, tuples, and dicts. 
        Replaces LazyResult, Router, and Inject.
        """
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            return self._resolve_lazy(obj, consumer_id, state_backend)
        
        elif isinstance(obj, Router):
            return self._resolve_router(obj, consumer_id, state_backend)
        
        elif isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)
        
        elif isinstance(obj, list):
            return [
                self._resolve_structure(item, consumer_id, state_backend, resource_context) 
                for item in obj
            ]
        
        elif isinstance(obj, tuple):
            return tuple(
                self._resolve_structure(item, consumer_id, state_backend, resource_context) 
                for item in obj
            )
        
        elif isinstance(obj, dict):
            return {
                k: self._resolve_structure(v, consumer_id, state_backend, resource_context)
                for k, v in obj.items()
            }
        
        return obj

    def _resolve_lazy(self, lr: LazyResult, consumer_id: str, state_backend: StateBackend) -> Any:
        if not state_backend.has_result(lr._uuid):
            # Check for skip
            if state_backend.get_skip_reason(lr._uuid):
                raise DependencyMissingError(
                    consumer_id, "unknown_arg", f"{lr._uuid} (skipped)"
                )
            raise DependencyMissingError(consumer_id, "unknown_arg", lr._uuid)
        
        return state_backend.get_result(lr._uuid)

    def _resolve_router(self, router: Router, consumer_id: str, state_backend: StateBackend) -> Any:
        # 1. Resolve Selector
        selector_uuid = router.selector._uuid
        if not state_backend.has_result(selector_uuid):
             raise DependencyMissingError(consumer_id, "router_selector", selector_uuid)
        
        selector_value = state_backend.get_result(selector_uuid)

        # 2. Pick Route
        try:
            selected_lr = router.routes[selector_value]
        except KeyError:
             raise ValueError(
                f"Router selector returned '{selector_value}', "
                f"but no matching route found in {list(router.routes.keys())}"
            )

        # 3. Resolve Route Result
        return self._resolve_lazy(selected_lr, consumer_id, state_backend)

    def _resolve_inject(self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]
        
        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any = None,
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    if state_backend.has_result(amount._uuid):
                         resolved[res] = state_backend.get_result(amount._uuid)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
~~~~~

#### Acts 6: 更新序列化逻辑

因为 `literal_inputs` 现在包含了复杂的对象，我们需要更新 `to_json` 逻辑来处理它们。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/serialize.py
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "literal_inputs": node.literal_inputs,  # Assumes JSON-serializable literals
    }

    if node.callable_obj:
~~~~~
~~~~~python
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type,
        "literal_inputs": _serialize_structure(node.literal_inputs),
    }

    if node.callable_obj:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/serialize.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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


def _serialize_structure(obj: Any) -> Any:
    """Recursively serializes structure, replacing LazyResult/Router with stubs."""
    if isinstance(obj, (LazyResult, MappedLazyResult)):
        return {"__lazy_ref": obj._uuid}
    elif isinstance(obj, Router):
        # We don't fully serialize router here as it's handled in the 'routers' section of the graph dict.
        # We just need a stub to indicate existence.
        # Actually, serialize.py separates routers.
        # But if a router is inside a list, we need to know.
        # For visualization simplicity, let's just mark it.
        return {"__router_ref": "complex_router"}
    elif isinstance(obj, list):
        return [_serialize_structure(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(_serialize_structure(x) for x in obj)
    elif isinstance(obj, dict):
        return {k: _serialize_structure(v) for k, v in obj.items()}
    return obj


def _edge_to_dict(edge: Edge, router_map: Dict[int, int]) -> Dict[str, Any]:
~~~~~

### 下一步建议
我们已经完成了核心重构。现在的 `GraphBuilder` 和 `ArgumentResolver` 支持任意深度的嵌套依赖，并且 `cs.inject` 有了明确的报错。
建议进行一次冒烟测试，尝试运行一个包含列表依赖（如 `task([a(), b()])`）的工作流，验证其是否能正确执行。同时尝试 `cs.dict` 和 `cs.format` 的使用。
