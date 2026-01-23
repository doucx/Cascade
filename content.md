好的，我们立即开始执行。

这是对“修复基础”路线图的全面实施，涵盖了从编译器到运行时的整个参数传递链路。我将根据您提供的 `diff` 生成一个统一的计划，该计划将一次性完成路线图的第二阶段和第三阶段，确保整个系统的端到端一致性。

## [WIP] refactor(core): 实现无损的 args/kwargs 参数流

### 用户需求

根据“修复基础”路线图的第二和第三阶段，全面重构从编译器到运行时的参数传递系统。这要求更新所有相关组件（IRGenerator, Expander, Wiring Policies, ComputeRequest, standard_launcher, SignatureBinder）以使用新的、无损的 `args`/`kwargs` 规约，取代旧的 `inputs` 字典。

### 评论

这是对系统核心的一次决定性重构。通过在整个调用链中强制执行无损的、与 Python 语义同构的 `args`/`kwargs` 结构，我们正在根除所有不确定性和启发式猜测。`SignatureBinder` 的最终简化是此次重构价值的最佳证明——一个更简单、更“愚笨”的组件，因为它建立在一个更智能、更可靠的基础之上，所以它更加坚固。

### 目标

1.  **校准编译器**：更新 `IRGenerator` 以生成包含 `args` 和 `kwargs` 的 `NodeIR`。
2.  **同构物理层**：更新 `Expander` 和相关策略，确保物理端口的创建与 `args`/`kwargs` 的结构严格对应。
3.  **纠正布线逻辑**：修复 `ParameterWiringPolicy` 中的核心错误，使其不再进行错误的端口名推断。
4.  **更新运行时契约**：修改 `ComputeRequest` 数据类以反映新的参数结构。
5.  **修复契约生产者**：重写 `standard_launcher` 的核心逻辑，使其能正确地从物理端口组装出新的 `ComputeRequest`。
6.  **简化契约消费者**：更新 `BridgedComputeService` 以消费新契约，并彻底简化 `SignatureBinder`，移除所有脆弱的参数解析逻辑。

### 基本原理

本次重构遵循“将复杂性前移”的核心原则。所有关于参数绑定的“智能”都被集中到了拥有最完整上下文的 `IRGenerator` 中。一旦它生成了无损的 `NodeIR`，这个确定性的信息就会在整个系统中无畸变地流动：

1.  `NodeIR` (`args`/`kwargs`) 被 `Expander` 翻译成**同构的**物理端口（以索引为名的 `args` 端口，以键为名的 `kwargs` 端口）。
2.  `standard_launcher` 根据这些确定性的端口名，**无损地**重组出 `ComputeRequest` (`input_args`/`input_kwargs`)。
3.  `SignatureBinder` 接收到与 Python 原始调用完全对应的 `args` 和 `kwargs`，从而可以依赖 `inspect` 模块进行**绝对可靠的**绑定。

这个单向、无损的数据流从根本上消除了信息丢失，从而修复了由其引发的所有下游 bug。

### 标签

#intent/refine #flow/ready #priority/critical #comp/compiler #comp/vm #comp/std #comp/spec #concept/parser #concept/executor #scope/core #scope/api #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 IR 规约与运行时契约 (Spec)

首先，我们奠定基础，修改 `NodeIR` 和 `ComputeRequest` 的定义。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    # V2 Argument Specification: Separated for clarity and determinism
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/contracts.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_refs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any]
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_args: List[Ref]
    input_kwargs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any]
~~~~~

#### Acts 2: 校准编译器以生产和消费新规约 (Compiler)

现在，我们将更新编译器前端和后端的所有组件，使其严格遵守新的 `NodeIR` 格式。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type=node_type,
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
            cache_policy=lr._cache_policy,
        )
~~~~~
~~~~~python.new
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type=node_type,
            logical_id=lr._uuid,
            args=transformed_args,
            kwargs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
            cache_policy=lr._cache_policy,
        )
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type="map",
            logical_id=lr._uuid,
            inputs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            retry_policy=self._extract_retry_policy(lr),
        )
~~~~~
~~~~~python.new
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type="map",
            logical_id=lr._uuid,
            # For map nodes, all inputs are keyword-based
            args=[],
            kwargs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            retry_policy=self._extract_retry_policy(lr),
        )
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # 2.2 Dynamic Args from Inputs
        for input_key in node_ir.inputs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")
~~~~~
~~~~~python.new
        # 2.2 Dynamic Args from Inputs
        # Positional args are represented by their index as a string
        for i in range(len(node_ir.args)):
            input_key = str(i)
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # Keyword args
        for input_key in node_ir.kwargs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
~~~~~
~~~~~python.old
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        for input_key, source_ref in node_ir.inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
~~~~~
~~~~~python.new
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # Combine args and kwargs for unified processing
        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # The port name is the key itself. We use it for naming debug nodes.
            port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~
~~~~~python.old
        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        for value in node_ir.inputs.values():
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break
~~~~~
~~~~~python.new
        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        all_input_values = list(node_ir.args) + list(node_ir.kwargs.values())
        for value in all_input_values:
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
~~~~~
~~~~~python.new
    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # The physical port name MUST be the input key itself (either digit for args or string for kwargs)
            # to ensure a direct mapping from IR to the physical graph.
            port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
~~~~~

#### Acts 3: 适配运行时与标准库 (Stdlib & VM)

最后，我们更新 `standard_launcher` 以生成新的 `ComputeRequest`，并简化 `BridgedComputeService` 和 `SignatureBinder` 以消费它。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/dyad/launcher.py
~~~~~
~~~~~python.old
@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    input_refs: Dict[str, Ref] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Iterate over dynamic args
    for port_name, input_token in io.args.items():
        # Check port definition in node for role
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            # Launcher expects inputs to be Refs (for compute) or values.
            # The Bleacher logic assumed payload was the value/ref.
            input_refs[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

        trace_payload.update(input_token.trace)

    # 2. Capture Metadata
    start_ts = time.time()  # Wall clock for IR
~~~~~
~~~~~python.new
@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    pos_args: Dict[int, Any] = {}
    input_kwargs: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Iterate over all connected input ports
    for port_name, input_token in io.args.items():
        if not input_token:
            continue

        port_def = node.input_ports[port_name]
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.DATA:
            if port_name.isdigit():
                pos_args[int(port_name)] = input_token.payload
            else:
                input_kwargs[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

    # Reconstruct the final positional args list from the sparse map.
    # We sort by the integer key to preserve the original argument order.
    input_args = [value for key, value in sorted(pos_args.items())]

    start_ts = time.time()  # Wall clock for IR
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/dyad/launcher.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_refs=input_refs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            with ExitStack() as stack:
                # 1. Resolve Inputs (Dereference Refs)
                raw_inputs: Dict[str, Any] = {
                    key: self.store.get(ref) for key, ref in request.input_refs.items()
                }

                # 2. Resolve Code
                func = self.registry.get(request.code_hash)

                # 3. Smart Binding & Injection
                binder = SignatureBinder(func, self.context)
                args, kwargs = binder.bind_and_resolve(raw_inputs, stack)

                # 4. Construct Proxy Node
                is_async = inspect.iscoroutinefunction(func)
~~~~~
~~~~~python.new
    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            with ExitStack() as stack:
                # 1. Resolve Inputs (Dereference Refs)
                # The request now carries pre-separated args and kwargs
                resolved_args = [self.store.get(ref) for ref in request.input_args]
                resolved_kwargs = {
                    key: self.store.get(ref) for key, ref in request.input_kwargs.items()
                }

                # 2. Resolve Code
                func = self.registry.get(request.code_hash)

                # 3. Smart Binding & Injection
                binder = SignatureBinder(func, self.context)
                args, kwargs = binder.bind_and_resolve(
                    resolved_args, resolved_kwargs, stack
                )

                # 4. Construct Proxy Node
                is_async = inspect.iscoroutinefunction(func)
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/binding.py
~~~~~
~~~~~python.old
    def bind_and_resolve(
        self, raw_inputs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # 1. Input Separation
        pos_inputs = {int(k): v for k, v in raw_inputs.items() if k.isdigit()}
        kw_inputs = {k: v for k, v in raw_inputs.items() if not k.isdigit()}

        # 2. System Parameter Injection
        # Ensure 'params_context' is available if requested by signature
        if "params_context" in self.sig.parameters and "params_context" not in kw_inputs:
            kw_inputs["params_context"] = self.context.params

        # 3. Reconstruct args_list based on signature consumption
        # This is critical to handle cases where positional args are sparse or skipped
        # because an earlier parameter was supplied via kwargs.
        args_list = []
        next_pos_idx = 0

        for param in self.sig.parameters.values():
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                # If this parameter is already satisfied by kwargs, it consumes no positional index.
                if param.name in kw_inputs:
                    continue

                # Otherwise, try to satisfy it from pos_inputs.
                if next_pos_idx in pos_inputs:
                    args_list.append(pos_inputs[next_pos_idx])
                    next_pos_idx += 1
                else:
                    # Missing positional argument. Let 'bind' handle the error or default value.
                    pass

            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                # *args consumes ALL remaining positional inputs, even if sparse.
                # We sort them to ensure deterministic order.
                remaining_keys = sorted([k for k in pos_inputs.keys() if k >= next_pos_idx])
                for k in remaining_keys:
                    args_list.append(pos_inputs[k])
                # No more positional consumption possible after *args
                break

        # 4. Bind
        try:
            bound = self.sig.bind(*args_list, **kw_inputs)
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for function '{self.func.__name__}': {e}"
            ) from e

        # Apply defaults (including Inject defaults)
        bound.apply_defaults()

        # 5. Recursive Resolution
        for name, value in bound.arguments.items():
            resolved = self._resolve_value(value, stack)
            if resolved is not value:
                bound.arguments[name] = resolved

        # Return the normalized arguments
        return bound.args, bound.kwargs
~~~~~
~~~~~python.new
    def bind_and_resolve(
        self, args: List[Any], kwargs: Dict[str, Any], stack: ExitStack
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # With the new IR spec, the caller is responsible for providing
        # clean args and kwargs. This binder's role is simplified.

        # 1. System Parameter Injection
        if "params_context" in self.sig.parameters and "params_context" not in kwargs:
            kwargs["params_context"] = self.context.params

        # 2. Bind
        try:
            bound = self.sig.bind(*args, **kwargs)
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for function '{self.func.__name__}': {e}"
            ) from e

        # 3. Apply defaults (including Inject defaults)
        bound.apply_defaults()

        # 5. Recursive Resolution
        for name, value in bound.arguments.items():
            resolved = self._resolve_value(value, stack)
            if resolved is not value:
                bound.arguments[name] = resolved

        # Return the normalized arguments
        return bound.args, bound.kwargs
~~~~~

### 下一步建议

我们已经完成了对核心参数传递系统的战略性重构。代码现在反映了一个确定性的、无损的信息流。

下一步是**阶段四：验证与巩固**。

我建议您现在执行 `pytest`。根据路线图的预测，所有 77 个之前失败的测试都应该通过。一旦测试通过，我们就可以进入最后一步：创建一个 `[COMMIT]` 计划，将这次重构作为一个完整的、里程碑式的变更提交到版本控制中。
