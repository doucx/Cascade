You are absolutely right. My previous patch was malformed, leading to a corrupted file and the syntax error. I apologize for that. Generating multiple complex changes within a single `patch_file` was a mistake.

I will now correct this by writing the complete, correct content for `resolvers.py`. This new version incorporates the data penetration logic for `cs.pipeline` and fixes the structural errors.

### [WIP] fix: 修复 resolvers.py 的语法错误并实现数据穿透

#### 错误分析
之前的 `patch_file` 操作是错误的。它试图将多个新方法的定义插入到文件中间，破坏了 `ArgumentResolver` 类的结构，导致了 `SyntaxError: unmatched ')'` 的解析错误。根本原因是 `patch_file` 的 `old_str` 和 `new_str` 选取不当，造成了混乱的合并。

#### 用户需求
使用 `write_file` 彻底覆盖 `packages/cascade-engine/src/cascade/runtime/resolvers.py`，提供一个语法正确且包含 `cs.pipeline` 数据穿透逻辑的完整版本。

#### 评论
这是一个典型的由于错误的 `patch` 策略导致的修复任务。正确的做法是，对于结构性或跨多个方法的变更，应使用 `write_file` 来保证文件的完整性和正确性，而不是尝试进行复杂且脆弱的 `patch` 操作。

#### 目标
1.  修正 `resolvers.py` 的语法错误。
2.  正确实现 `ArgumentResolver` 中 `cs.pipeline` 所需的数据穿透逻辑。

#### 基本原理
我将重新构建 `ArgumentResolver` 类的逻辑，确保 `graph` 对象被正确地从顶层 `resolve` 方法一路传递到 `_resolve_lazy` 方法。`_resolve_lazy` 将包含新的逻辑：当一个任务被跳过时，它会查询 `graph`，找到该任务的数据输入源，并尝试解析该源的值作为替代输出。

#### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/graph #ai/instruct #task/domain/core #task/object/flow-primitives #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重写 resolvers.py
我们将使用 `write_file` 来提供 `resolvers.py` 的完整、正确内容。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


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

        # Recursively resolve the structure, passing the graph for context
        resolved_structure = self._resolve_structure(
            node.literal_inputs, node.id, state_backend, resource_context, graph
        )

        # Re-assemble args and kwargs
        final_kwargs = {k: v for k, v in resolved_structure.items() if not k.isdigit()}
        positional_args_dict = {
            int(k): v for k, v in resolved_structure.items() if k.isdigit()
        }

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # Handle Inject in defaults (if not overridden by inputs)
        if node.signature:
            for param in node.signature.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
        elif node.callable_obj:
            # Fallback if signature wasn't cached for some reason
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in final_kwargs:
                        final_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        return args, final_kwargs

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        """
        Recursively traverses lists, tuples, and dicts.
        Replaces LazyResult, Router, and Inject.
        """
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            return self._resolve_lazy(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Router):
            return self._resolve_router(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)

        elif isinstance(obj, list):
            return [
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            ]

        elif isinstance(obj, tuple):
            return tuple(
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            )

        elif isinstance(obj, dict):
            return {
                k: self._resolve_structure(
                    v, consumer_id, state_backend, resource_context, graph
                )
                for k, v in obj.items()
            }

        return obj

    def _resolve_lazy(
        self,
        lr: LazyResult,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        if not state_backend.has_result(lr._uuid):
            # Check for skip. If skipped, attempt data penetration for pipelines.
            if state_backend.get_skip_reason(lr._uuid):
                # Find the skipped node's primary data input
                for edge in graph.edges:
                    if edge.target.id == lr._uuid and edge.edge_type == EdgeType.DATA:
                        # Found an upstream data source. Recursively resolve it.
                        # This assumes a simple pipeline structure (one main data input).
                        source_lr_stub = LazyResult(
                            task=None, args=(), kwargs={}, _uuid=edge.source.id
                        )
                        try:
                            return self._resolve_lazy(
                                source_lr_stub, consumer_id, state_backend, graph
                            )
                        except DependencyMissingError:
                            # If the upstream of the skipped node is ALSO missing, then we fail.
                            pass

                # If penetration fails or it's not a pipeline-like structure, raise.
                raise DependencyMissingError(
                    consumer_id, "unknown_arg", f"{lr._uuid} (skipped)"
                )

            raise DependencyMissingError(consumer_id, "unknown_arg", lr._uuid)

        return state_backend.get_result(lr._uuid)

    def _resolve_router(
        self, router: Router, consumer_id: str, state_backend: StateBackend, graph: Graph
    ) -> Any:
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
        return self._resolve_lazy(selected_lr, consumer_id, state_backend, graph)

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
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

### 下一步建议
现在文件已被修复，请重新运行 `pytest tests/engine/runtime/test_flow_primitives.py` 来验证所有新功能和修复是否按预期工作。
