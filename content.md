Excellent. We've cleared the major structural errors, and now we're down to a smaller, more focused set of logical bugs and adaptation tasks. This is great progress.

Let's break down the remaining failures.

## [WIP] fix(core): Correct Router resolution and finalize data model adaptation

### 错误分析
当前的 8 个失败指向了三个 distinct 的问题：

1.  **Router 逻辑错误 (AssertionError & DID NOT RAISE)**: `test_router_pruning.py` 和 `test_routing.py` 中的所有失败都显示，`Engine` 错误地将 `Router` 的 *selector* 的值（例如 "a"）作为最终结果，而不是去执行被选中的 *route*（例如 `task_a`）并返回其结果（"A"）。这是 `ArgumentResolver` 中的一个核心逻辑缺陷。它没有正确地“解引用”`Router` 对象。

2.  **SDK 工具未适配 (AttributeError)**: `test_preview.py` 仍然失败，因为它依赖的 `PlanNodeInspected` 事件和 `_analyze_plan` 函数还在引用已删除的 `literal_inputs` 属性。

3.  **测试断言错误 (TypeError)**: `test_serialize.py` 的失败是由于我上次修复引入的一个错误断言。`"__slot_ref" in param_node["input_bindings"]["name"]` 试图在一个 `SlotRef` 对象上进行迭代，这是不允许的。

### 用户需求
修复上述三个问题，使测试套件完全通过，从而正式完成“The Great Split”重构的第一步。

### 评论
我们已经非常接近终点。修复 `ArgumentResolver` 是最后的核心逻辑挑战，它将使 `Router` 这一关键动态特性在新数据模型下恢复正常工作。其余的都是对工具和测试的直接适配。

### 目标
1.  重构 `ArgumentResolver` 以正确处理 `Router` 对象的解析。
2.  更新 `cascade-sdk` 中的 `preview` 工具及其相关事件，使其使用 `input_bindings`。
3.  修正 `test_serialize.py` 中错误的 `TypeError` 断言。

### 基本原理
我们将重写 `ArgumentResolver` 中的依赖解析逻辑，使其在遇到附带 `Router` 的边时，首先解析 `selector` 的值，然后用该值从 `Router` 的 `routes` 字典中选择正确的上游 `LazyResult`，最后再解析这个被选中的 `LazyResult` 的结果。对于 SDK 工具，我们将完成从 `literal_inputs` 到 `input_bindings` 的迁移。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/sdk #comp/tests #concept/routing #scope/core #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复核心 Router 解析逻辑

这是最关键的修复。我们将重构 `ArgumentResolver`，使其能正确“解引用”Router。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple, Optional

from cascade.graph.model import Node, Graph, Edge, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.binding import SlotRef, Constant
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (SlotRefs pointing to DataTuple)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        data_tuple: Tuple[Any, ...],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings + DataTuple
        positional_args_dict = {}
        for name, binding in node.input_bindings.items():
            value = self._resolve_binding(binding, data_tuple)
            
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(value, node.id, state_backend, resource_context, graph)

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]
        
        # 2. Overlay Dependencies from Edges
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(edge, node.id, state_backend, graph)
                
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    kwargs[edge.arg_name] = val

        # 3. Handle Resource Injection in Defaults
        if node.signature:
            # Create a bound arguments object to see which args are not yet filled
            try:
                bound_args = node.signature.bind_partial(*args, **kwargs)
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject) and param.name not in bound_args.arguments:
                        kwargs[param.name] = self._resolve_inject(param.default, node.name, resource_context)
            except TypeError:
                # This can happen if args/kwargs are not yet valid, but we can still try a simpler check
                pass

        # 4. Handle internal param fetching context
        from cascade.internal.inputs import _get_param_value
        if node.callable_obj is _get_param_value.func:
             kwargs["params_context"] = user_params or {}

        return args, kwargs

    def _resolve_binding(self, binding: Any, data_tuple: Tuple[Any, ...]) -> Any:
        if isinstance(binding, SlotRef):
            return data_tuple[binding.index]
        elif isinstance(binding, Constant):
            return binding.value
        return binding

    def _resolve_structure(
        self, obj: Any, consumer_id: str, state_backend: StateBackend,
        resource_context: Dict[str, Any], graph: Graph,
    ) -> Any:
        if isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)
        elif isinstance(obj, list):
            return [self._resolve_structure(item, consumer_id, state_backend, resource_context, graph) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._resolve_structure(item, consumer_id, state_backend, resource_context, graph) for item in obj)
        elif isinstance(obj, dict):
            return {k: self._resolve_structure(v, consumer_id, state_backend, resource_context, graph) for k, v in obj.items()}
        return obj

    def _resolve_dependency(
        self, edge: Edge, consumer_id: str, state_backend: StateBackend, graph: Graph
    ) -> Any:
        # ** CORE ROUTER LOGIC FIX **
        if edge.router:
            # This edge represents a Router. Its source is the SELECTOR.
            # We must resolve the selector's value first.
            selector_result = self._get_node_result(edge.source.id, consumer_id, "router_selector", state_backend, graph)
            
            # Use the result to pick the correct route.
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )
            
            # Now, resolve the result of the SELECTED route.
            return self._get_node_result(selected_route_lr._uuid, consumer_id, edge.arg_name, state_backend, graph)
        else:
            # Standard dependency
            return self._get_node_result(edge.source.id, consumer_id, edge.arg_name, state_backend, graph)

    def _get_node_result(
        self, node_id: str, consumer_id: str, arg_name: str, 
        state_backend: StateBackend, graph: Graph
    ) -> Any:
        """Helper to get a node's result, with skip penetration logic."""
        if state_backend.has_result(node_id):
            return state_backend.get_result(node_id)
        
        if state_backend.get_skip_reason(node_id):
            upstream_edges = [e for e in graph.edges if e.target.id == node_id]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
            if data_inputs:
                # Recursively try to penetrate the skipped node
                return self._get_node_result(data_inputs[0].source.id, consumer_id, arg_name, state_backend, graph)

        skip_info = f" (skipped: {state_backend.get_skip_reason(node_id)})" if state_backend.get_skip_reason(node_id) else ""
        raise DependencyMissingError(consumer_id, arg_name, f"{node_id}{skip_info}")

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]
        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)
~~~~~

#### Acts 2: 适配 SDK Preview 工具

首先，更新 `events.py` 中的事件定义。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""

    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "literal_inputs": self.literal_inputs,
        }
~~~~~
~~~~~python
@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""

    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "input_bindings": self.input_bindings,
        }
~~~~~

然后，更新 `preview.py` 的逻辑和视图以使用 `input_bindings`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~
~~~~~python
            # Filter out non-literal dependencies from the inputs for cleaner output
            from cascade.spec.lazy_types import LazyResult, MappedLazyResult

            literals = {
                k: v
                for k, v in node.literal_inputs.items()
                if not isinstance(v, (LazyResult, MappedLazyResult))
            }

            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    literal_inputs=literals,
                )
            )
~~~~~
~~~~~python
            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    input_bindings=node.input_bindings,
                )
            )
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~
~~~~~python
    def on_node(self, event: PlanNodeInspected):
        # Format literal inputs for readability
        literals_repr = {
            k: (f"<LazyResult of '{v.task.name}'>" if isinstance(v, LazyResult) else v)
            for k, v in event.literal_inputs.items()
        }
        print(
            f"[{event.index}/{event.total_nodes}] {event.node_name} (Literals: {literals_repr})"
        )
~~~~~
~~~~~python
    def on_node(self, event: PlanNodeInspected):
        # Format input bindings for readability
        bindings_repr = {
            k: repr(v) for k, v in event.input_bindings.items()
        }
        print(
            f"[{event.index}/{event.total_nodes}] {event.node_name} (Bindings: {bindings_repr})"
        )
~~~~~

#### Acts 3: 修复 `test_serialize.py` 的断言

将错误的 `in` 检查替换为 `isinstance`。

~~~~~act
patch_file
tests/engine/graph/test_serialize.py
~~~~~
~~~~~python
    assert param_node["node_type"] == "task"
    assert "__slot_ref" in param_node["input_bindings"]["name"]

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "__slot_ref" in p_node.input_bindings["name"]
~~~~~
~~~~~python
    from cascade.spec.binding import SlotRef

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert "__slot_ref" in param_node["input_bindings"]["name"]

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert isinstance(p_node.input_bindings["name"], SlotRef)
~~~~~

### 下一步建议
我们已经解决了所有已知的逻辑错误和适配问题。这次修复应该能让测试套件完全通过。请再次运行 `pytest`。如果所有测试都通过，我们可以自信地宣布 **[COMMIT 1] The Great Split** 已经完成。
