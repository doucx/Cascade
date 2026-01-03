You are absolutely right. My apologies. This is the exact same class of error as the last one, and it stems from the same oversight in my previous refactoring. I failed to update all the call sites that depended on the now-removed `node.callable_obj` attribute. `ArgumentResolver` also needs the callable to inspect for `Inject` markers in default arguments, and I missed it.

Thank you for catching this. It's a critical bug. I will now generate a plan to fix it by applying the same principle: explicitly passing the callable object where it's needed.

## [WIP] fix(engine): Pass executable to ArgumentResolver to fix AttributeError

### 错误分析
在移除 `Node.callable_obj` 的过程中，我未能更新 `ArgumentResolver` 的实现。该解析器依赖于访问 `callable_obj` 来执行两项关键任务：
1.  通过 `inspect.signature` 检查函数签名的默认参数，以发现并注入 `Inject` 标记的资源。
2.  识别 `_get_param_value` 任务，为其注入 `params_context`。

由于 `callable_obj` 不再存在于 `Node` 对象上，这导致了您所报告的 `AttributeError`。

### 用户需求
修复在 `ArgumentResolver` 中因访问不存在的 `node.callable_obj` 属性而导致的 `AttributeError`。

### 评论
这个修复进一步加强了我们新架构的稳健性。它强制 `ArgumentResolver` 的依赖关系变得明确：如果它需要一个 callable 来完成工作，那么这个 callable 必须作为显式参数传递给它。这消除了对 `Node` 对象内部状态的隐式依赖，使代码更清晰、更易于测试。

### 目标
1.  修改 `ArgumentResolver.resolve` 的方法签名，使其接受一个 `callable_obj` 参数。
2.  更新 `ArgumentResolver` 的内部逻辑，使用传入的 `callable_obj` 参数进行签名检查和任务类型判断。
3.  在 `GraphExecutionStrategy` 中，从 `executable_registry` 查找正确的 callable，并将其传递给 `ArgumentResolver`。

### 基本原理
我们通过依赖注入来解决这个问题。`GraphExecutionStrategy` 作为协调者，拥有 `Graph`（数据）和 `ExecutableRegistry`（实现）。当它调用需要实现的 `ArgumentResolver` 时，它有责任将这两者结合起来，提供 `ArgumentResolver` 完成其工作所需的所有信息。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 ArgumentResolver 以接收 Callable

我们将修改 `ArgumentResolver.resolve` 以显式接收 `callable_obj`，并更新其内部逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python.old
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
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
            # Reconstruct args/kwargs from Bindings (Literals) and Overrides
            bindings = node.input_bindings
            if input_overrides:
                bindings = bindings.copy()
                bindings.update(input_overrides)

            # 1. Fill from bindings
            f_args: List[Any] = []
            f_kwargs: Dict[str, Any] = {}
            for k, v in bindings.items():
                if k.isdigit():
                    idx = int(k)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = v
                else:
                    f_kwargs[k] = v

            # 2. Fill from edges using the unified helper
            resolved_edge_values = await self._resolve_data_edges(
                node, graph, state_backend, instance_map, input_overrides
            )
            for k, v in resolved_edge_values.items():
                if k.isdigit():
                    idx = int(k)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = v
                else:
                    f_kwargs[k] = v

            return f_args, f_kwargs

        # --- COMPLEX PATH ---
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            # Always resolve structures to handle nested Injects correctly
            value = self._resolve_structure(
                value_raw,
                node.current_node_instance_hash,
                state_backend,
                resource_context,
                graph,
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges using the unified helper
        resolved_edge_values = await self._resolve_data_edges(
            node, graph, state_backend, instance_map, input_overrides
        )
        for k, v in resolved_edge_values.items():
            if k.isdigit():
                idx = int(k)
                while len(args) <= idx:
                    args.append(None)
                args[idx] = v
            else:
                kwargs[k] = v

        # 3. Handle Resource Injection in Defaults
        if node.callable_obj:
            try:
                # Re-inspect signature on demand
                sig = inspect.signature(node.callable_obj)
                bound_args = sig.bind_partial(*args, **kwargs)
                for param in sig.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except (ValueError, TypeError):
                pass

        # 4. Handle internal param fetching context
        # [CRITICAL] This logic must always run for Param tasks
        from cascade.common.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}

        return args, kwargs
~~~~~
~~~~~python.new
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        callable_obj: Optional[Callable],
        user_params: Optional[Dict[str, Any]] = None,
        input_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
            # Reconstruct args/kwargs from Bindings (Literals) and Overrides
            bindings = node.input_bindings
            if input_overrides:
                bindings = bindings.copy()
                bindings.update(input_overrides)

            # 1. Fill from bindings
            f_args: List[Any] = []
            f_kwargs: Dict[str, Any] = {}
            for k, v in bindings.items():
                if k.isdigit():
                    idx = int(k)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = v
                else:
                    f_kwargs[k] = v

            # 2. Fill from edges using the unified helper
            resolved_edge_values = await self._resolve_data_edges(
                node, graph, state_backend, instance_map, input_overrides
            )
            for k, v in resolved_edge_values.items():
                if k.isdigit():
                    idx = int(k)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = v
                else:
                    f_kwargs[k] = v

            return f_args, f_kwargs

        # --- COMPLEX PATH ---
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            # Always resolve structures to handle nested Injects correctly
            value = self._resolve_structure(
                value_raw,
                node.current_node_instance_hash,
                state_backend,
                resource_context,
                graph,
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges using the unified helper
        resolved_edge_values = await self._resolve_data_edges(
            node, graph, state_backend, instance_map, input_overrides
        )
        for k, v in resolved_edge_values.items():
            if k.isdigit():
                idx = int(k)
                while len(args) <= idx:
                    args.append(None)
                args[idx] = v
            else:
                kwargs[k] = v

        # 3. Handle Resource Injection in Defaults
        if callable_obj:
            try:
                # Re-inspect signature on demand
                sig = inspect.signature(callable_obj)
                bound_args = sig.bind_partial(*args, **kwargs)
                for param in sig.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except (ValueError, TypeError):
                pass

        # 4. Handle internal param fetching context
        # [CRITICAL] This logic must always run for Param tasks
        from cascade.common.inputs import _get_param_value

        if callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}

        return args, kwargs
~~~~~

#### Acts 2: 更新 GraphExecutionStrategy 中的调用点

我们更新 `GraphExecutionStrategy`，以将正确的 `executable` 传递给 `ArgumentResolver`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                        inputs = await self.node_processor.arg_resolver.resolve(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            instance_map=instance_map,
                            user_params=params,
                            input_overrides=overrides,
                        )

                        cache_inputs = (
                            await self.node_processor.arg_resolver.resolve_cache_inputs(
                                node, graph, state_backend
                            )
                        )

                        executable = executable_registry[node.current_node_instance_hash]

                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    executable,
                                    inputs,
~~~~~
~~~~~python.new
                        executable = executable_registry[node.current_node_instance_hash]

                        inputs = await self.node_processor.arg_resolver.resolve(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            instance_map=instance_map,
                            callable_obj=executable,
                            user_params=params,
                            input_overrides=overrides,
                        )

                        cache_inputs = (
                            await self.node_processor.arg_resolver.resolve_cache_inputs(
                                node, graph, state_backend
                            )
                        )

                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    executable,
                                    inputs,
~~~~~

### 下一步建议
好了，这个疏忽现在已经修复。`ArgumentResolver` 和 `ResourceContainer` 都已更新为使用新的 `ExecutableRegistry` 模式。

我们现在可以继续执行原计划的**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。我将生成执行此步骤的计划。
