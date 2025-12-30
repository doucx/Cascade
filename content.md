## [WIP] refactor(runtime): 增强参数解析器的签名绑定能力并标准化 ParamNode 执行

3.  **用户需求**:
    *   修复 TCO 场景下 `input_overrides` 无法覆盖位置参数 Edge 的 Bug。
    *   移除 `ArgumentResolver` 中 `ParamNode` 直接写入结果的副作用代码。
    *   实现 `ArgumentResolver` 自动将 `user_params` 注入到 `ParamNode` 的执行参数中。

4.  **评论**:
    当前的参数解析逻辑过于简单，通过字符串匹配来处理覆盖（Override），这在位置参数与关键字参数混用时会失效。引入 `inspect.Signature.bind` 是解决此问题的标准做法，它能将所有输入归一化。此外，`ParamNode` 的标准化执行将使运行时流程更加统一和可预测。

5.  **目标**:
    1.  在 `ArgumentResolver` 中实现基于 Signature 的参数归一化逻辑。
    2.  利用归一化后的参数名，准确判断 `input_overrides` 是否应该屏蔽某些 Edge。
    3.  移除 `ParamNode` 的特殊执行分支，改为注入 `params_context`。

6.  **基本原理**:
    *   **签名绑定 (Signature Binding)**: 只有通过函数的 Signature，我们才能知道第 0 个位置参数其实叫 "n"。这是正确处理 `Jump(data={"n": ...})` 覆盖 `f(cs.Param("n"))` 这种位置依赖的关键。
    *   **依赖注入**: `ParamNode` 本质上是一个这就需要外部环境（`params`）的任务。通过 Resolver 将环境作为参数注入，保持了节点的纯函数特性（在给定环境下的纯函数）。

7.  **标签**:
    #intent/refine #intent/fix #flow/ready #priority/high
    #comp/runtime #concept/resolver #scope/core
    #ai/instruct
    #task/domain/core #task/object/argument-resolver #task/action/refactor #task/state/continue

8.  **脚本**:

### Script

#### Acts 1: 重构 ArgumentResolver
这是本次重构的核心。我们将完全重写 `resolve` 方法的核心逻辑。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from typing import Any, Dict, List, Tuple, Optional
import inspect

from cascade.graph.model import Node, Graph, Edge, EdgeType, ParamNode
from cascade.spec.resource import Inject
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Optional[Dict[str, Any]] = None,
        input_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        # 1. 准备基础数据
        input_overrides = input_overrides or {}
        bindings = node.input_bindings.copy()
        
        # 2. 获取签名以便归一化
        sig = None
        if node.callable_obj:
            try:
                sig = inspect.signature(node.callable_obj)
            except ValueError:
                pass
        
        # 3. 如果是 ParamNode，从属性中恢复 key 到 bindings
        # (Phase 1 虽然让 ParamNode 有了 input_bindings，但在这里做个防御性编程或注入逻辑)
        if isinstance(node, ParamNode):
            # ParamNode 的 callable 是 _get_param_value(name, params_context)
            # 我们需要注入 params_context
            bindings["params_context"] = user_params or {}
            # 确保 name 存在 (从 param_key)
            if node.param_key and "name" not in bindings and "0" not in bindings:
                bindings["name"] = node.param_key

        # 4. 收集所有 Edge 依赖
        # 这里我们先不根据 Override 过滤，而是把所有 Edge 收集起来
        # 然后通过 Signature 统一处理冲突
        edge_values = {}
        incoming_edges = [
            e
            for e in graph.edges
            if e.target.structural_id == node.structural_id
            and e.edge_type == EdgeType.DATA
        ]
        
        for edge in incoming_edges:
            val = await self._resolve_dependency(
                edge, node.structural_id, state_backend, graph, instance_map
            )
            edge_values[edge.arg_name] = val

        # 5. 为了处理 Override，我们需要将所有输入（Bindings, Edges）映射到参数名
        # 策略：
        # - 如果有 Signature，利用它将所有 位置参数 (包括 "0", "1"...) 转换为 名字。
        # - 如果没有 Signature，只能信任名称匹配。
        
        final_kwargs = {}
        
        # 5.1 合并 Bindings 和 Edges 到一个“位置+关键字”的混合视图
        # positionals map: index -> value
        positionals: Dict[int, Any] = {}
        # keywords map: name -> value
        keywords: Dict[str, Any] = {}
        
        def merge_to_view(source: Dict[str, Any]):
            for k, v in source.items():
                if k.isdigit():
                    idx = int(k)
                    positionals[idx] = v
                else:
                    keywords[k] = v
        
        merge_to_view(bindings)
        merge_to_view(edge_values)
        
        # 5.2 应用 Overrides 的初步过滤
        # 如果 Override 提供了 keyword，我们可以直接从 keywords 中移除对应的 entry
        # 但我们无法轻易移除 positionals，因为不知道 positional 对应的名字是什么
        for k, v in input_overrides.items():
            if k in keywords:
                # Override 覆盖了静态绑定
                # 我们稍后会把 override 加回去，这里先删掉静态的避免冲突
                del keywords[k]
                
        # 5.3 利用 Signature 进行归一化 (Binding)
        if sig:
            # 构造用于 bind 的参数列表/字典
            # max index in positionals
            max_idx = max(positionals.keys()) if positionals else -1
            args_list = []
            for i in range(max_idx + 1):
                if i in positionals:
                    args_list.append(self._resolve_structure(positionals[i], node.structural_id, state_backend, resource_context, graph))
                else:
                    # Missing positional? 
                    # Signature bind might catch this, or it's optional. 
                    # We utilize a placeholder or rely on default.
                    # Actually, bind_partial allow missing.
                    # But we can't pass "holes" to bind. 
                    # Strategy: Only bind what we have. If we have [0, 2], we can't bind easily.
                    # Simpler Strategy: Cascde Graph usually fills positionals contiguously.
                    # If not, it assumes defaults.
                    pass
            
            # 由于 bind 需要连续的位置参数，我们先尽量填充。
            # 实际上，Input Bindings 是完整的。Edge 也是明确的。
            # 我们尝试构建 bound_arguments
            
            # 但是，Overrides 是最高优先级的。
            # 如果 Override 已经提供了某个参数 'n'，我们根本不应该把 'n' 对应的 Edge 值传给 bind。
            # 否则 bind 会报错 "multiple values for 'n'".
            
            # 所以，正确的顺序是：
            # 1. 识别出 Override 覆盖了哪些参数名。
            # 2. 从 positionals 和 keywords 中剔除这些参数。
            
            # 要做到第 2 点，必须先知道 positionals 对应什么名字。
            parameters = list(sig.parameters.values())
            
            # 筛选后的 args/kwargs
            filtered_args = []
            filtered_kwargs = keywords.copy()
            
            # 处理位置参数
            # 我们遍历 positionals (假设有序且从0开始)，并对照 Signature 的 parameters
            # 如果对应位置的 param.name 在 overrides 里，就丢弃该 positional。
            # 否则，保留。
            
            # 注意：Positionals 必须保持此时的相对顺序，如果丢弃中间一个，后面的会前移？ 
            # 不！Python函数调用不允许跳过位置。
            # 如果 Override 覆盖了第 0 个位置参数（通过名字），那么第 0 个位置必须由 Override 提供的值填充？
            # 不，Override 通常以 keyword 形式提供。
            # Python allow: func(1, n=2) -> Error if 1 is for n.
            # Python allow: func(n=2) -> OK.
            
            # 所以，如果 parameters[i].name 在 overrides 中：
            # 我们不能传递 args_list[i]。也就是说，args_list 必须在该处截断？ 
            # 或者该位置参数不再作为位置参数传递，而是假设它被 keyword 替代了。
            
            # 结论：如果有 Signature，我们应该尽早把所有 input 转换为 kwargs 形式，
            # 这样处理 Overrides 就变成了简单的字典 update。
            
            unified_kwargs = {}
            
            # A. 映射 Bindings/Edges 到 unified_kwargs
            # A.1 Keywords
            for k, v in keywords.items():
                unified_kwargs[k] = self._resolve_structure(v, node.structural_id, state_backend, resource_context, graph)
                
            # A.2 Positionals
            # 我们需要处理 inject/structure
            resolved_positionals = {
                k: self._resolve_structure(v, node.structural_id, state_backend, resource_context, graph)
                for k, v in positionals.items()
            }
            
            for i in sorted(resolved_positionals.keys()):
                if i < len(parameters):
                    param = parameters[i]
                    # 如果 param 是 POSITIONAL_ONLY，我们必须保留在位置参数列表里？
                    # 或者我们可以暂时放在 kwargs 里，最后组装的时候再转回去？
                    # Python < 3.8 没有 POSITIONAL_ONLY (除了 C ext)。
                    # 但 inspect 支持。Cascade Task 目前大多是普通函数。
                    # 为了最大兼容性，我们尝试映射名字。
                    if param.kind == inspect.Parameter.VAR_POSITIONAL:
                        # *args 收集剩余的
                        # 这比较复杂，暂不支持 *args 的部分参数被 override.
                        # 对于 Cascade 图，*args 通常作为一个整体列表传递。
                        pass
                    else:
                        unified_kwargs[param.name] = resolved_positionals[i]
                else:
                    # 超出签名的位置参数？可能是 *args
                    pass
            
            # B. 应用 Overrides
            unified_kwargs.update(input_overrides)
            
            # C. 处理 Injects (Defaults)
            # 对于没有提供的参数，检查是否有 Inject 默认值
            for param in parameters:
                if param.name not in unified_kwargs:
                    if isinstance(param.default, Inject):
                        unified_kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            
            # D. 重组为 args, kwargs 调用
            final_args = []
            final_kwargs = {}
            
            # 再次遍历 Signature，决定哪些放 args，哪些放 kwargs
            for param in parameters:
                if param.name in unified_kwargs:
                    val = unified_kwargs[param.name]
                    if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                        final_args.append(val)
                    elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                        # 如果 unified_kwargs 里有 *args 的名字？通常不应该。
                        # 支持有限。
                        final_kwargs[param.name] = val
                    elif param.kind == inspect.Parameter.VAR_KEYWORD:
                        # **kwargs
                        final_kwargs.update(val) if isinstance(val, dict) else None
                    else:
                        # POSITIONAL_OR_KEYWORD or KEYWORD_ONLY
                        # 偏好 Keyword 以避免歧义
                        final_kwargs[param.name] = val
            
            return final_args, final_kwargs

        else:
            # 没有 Signature，退回到简单的合并策略
            # 这是旧逻辑的增强版
            resolved_args = []
            resolved_kwargs = {}
            
            # Positionals
            max_idx = max(positionals.keys()) if positionals else -1
            for i in range(max_idx + 1):
                if i in positionals:
                    val = self._resolve_structure(positionals[i], node.structural_id, state_backend, resource_context, graph)
                    resolved_args.append(val)
                else:
                    resolved_args.append(None) # Hole?
            
            # Keywords
            for k, v in keywords.items():
                if k not in input_overrides:
                    resolved_kwargs[k] = self._resolve_structure(v, node.structural_id, state_backend, resource_context, graph)
            
            # Apply Overrides
            # 注意：没有 Signature，我们无法知道 input_overrides 是否覆盖了 resolved_args[0]
            # 这就是 Bug 发生的地方。
            # 但既然没有 sig，用户也就是瞎猜。
            resolved_kwargs.update(input_overrides)
            
            return resolved_args, resolved_kwargs

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        if isinstance(obj, Inject):
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

    async def _resolve_dependency(
        self,
        edge: Edge,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
        instance_map: Dict[str, Node],
    ) -> Any:
        if edge.router:
            # Router Logic
            selector_result = await self._get_node_result(
                edge.source.structural_id,
                consumer_id,
                "router_selector",
                state_backend,
                graph,
            )
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                 # TODO: Better error message including available routes
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )
            selected_node = instance_map[selected_route_lr._uuid]
            return await self._get_node_result(
                selected_node.structural_id,
                consumer_id,
                edge.arg_name,
                state_backend,
                graph,
            )
        else:
            return await self._get_node_result(
                edge.source.structural_id,
                consumer_id,
                edge.arg_name,
                state_backend,
                graph,
            )

    async def _get_node_result(
        self,
        node_id: str,
        consumer_id: str,
        arg_name: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        if await state_backend.has_result(node_id):
            return await state_backend.get_result(node_id)

        skip_reason = await state_backend.get_skip_reason(node_id)
        if skip_reason:
            # Try Penetration
            upstream_edges = [
                e for e in graph.edges if e.target.structural_id == node_id
            ]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
            if data_inputs:
                return await self._get_node_result(
                    data_inputs[0].source.structural_id,
                    consumer_id,
                    arg_name,
                    state_backend,
                    graph,
                )

        skip_info = f" (skipped: {skip_reason})" if skip_reason else ""
        raise DependencyMissingError(consumer_id, arg_name, f"{node_id}{skip_info}")

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]
        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)
      
class ConstraintResolver:
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any,
        instance_map: Dict[str, Node],
    ) -> Dict[str, Any]:
        resolved = {}
        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                # Use uuid check to detect dynamic reference
                # (Simple heuristic, could be improved)
                if hasattr(amount, "_uuid"): 
                     constraint_node = instance_map.get(amount._uuid)
                     if not constraint_node:
                         raise DependencyMissingError(
                             node.structural_id, f"constraint:{res}", amount._uuid
                         )
                     if await state_backend.has_result(constraint_node.structural_id):
                         resolved[res] = await state_backend.get_result(constraint_node.structural_id)
                     else:
                         raise DependencyMissingError(
                            node.structural_id,
                            f"constraint:{res}",
                            constraint_node.structural_id,
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
~~~~~
