## [WIP] refactor(compiler): 为参数传递重新定义确定性的 IR 规约

### 错误分析

连续的 `TypeError` 和 `IndexError` 表明，根本问题不在于 `SignatureBinder` 的实现细节，而在于它所接收的数据结构 `raw_inputs`（源自 `NodeIR.inputs`）是信息有损且语义模糊的。该扁平字典无法区分位置参数和关键字参数，迫使绑定器进行脆弱的猜测，从而在处理 `*args` 等复杂签名时必然失败。

### 用户需求

建立一个能够无歧义地处理任何复杂 Python 函数签名的、确定性的参数传递系统。

### 评论

这是一次必要的架构重构。通过修复 IR（系统内部的“API契约”），我们可以简化所有与之交互的组件（生产者和消费者），并消除一整类潜在的绑定错误。这完全符合 HFEA（高保真工程公理）协议的精神。

### 目标

1.  **修改规约**: 在 `cascade-spec` 中，更新 `NodeIR` 数据结构，用明确的 `args` 和 `kwargs` 字段取代模糊的 `inputs` 字段。
2.  **更新生产者**: 在 `cascade-compiler` 中，修改 `IRGenerator` 以生成符合新规约的 `NodeIR` 实例。
3.  **简化消费者**: 在 `cascade-vm` 中，简化 `SignatureBinder`，移除所有参数重构逻辑，使其直接处理干净的 `args` 和 `kwargs`。

### 基本原理

我们将通过强化 `NodeIR` 这个核心数据契约，将参数绑定的复杂性从运行时（VM）转移到编译时（Compiler）。编译器拥有完整的 DSL 上下文，能够无歧义地分离位置参数和关键字参数。这使得运行时的绑定过程变得简单、快速且无懈可击。

### 标签

#intent/architect #intent/refine #flow/ready #priority/critical #comp/spec #comp/compiler #comp/runtime #scope/api #scope/core #ai/brainstorm #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修改 `cascade-spec`，重新定义 NodeIR 规约

我们将首先修改 `NodeIR` 的定义，使其具有确定性的参数字段。

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

#### Acts 2: 更新 `cascade-compiler`，使其生成符合新规约的 IR

现在，我们将修改 `IRGenerator` 以填充新的 `args` 和 `kwargs` 字段。

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

#### Acts 3: 简化 `cascade-vm` 的 `SignatureBinder`

最后，我们将移除 `SignatureBinder` 中所有复杂的、脆弱的参数重构逻辑。

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

        # 3. Reconstruct args_list, excluding any params already covered by kwargs.
        args_list = []
        params = list(self.sig.parameters.values())
        has_var_positional = any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
        )

        max_pos_arg = -1
        if pos_inputs:
            max_pos_arg = max(pos_inputs.keys())

        for i in range(max_pos_arg + 1):
            # We only add a positional argument to the list if its corresponding
            # parameter is not already provided as a keyword argument.
            is_in_kwargs = False
            if i < len(params):
                param = params[i]
                if param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.POSITIONAL_ONLY,
                ):
                    if param.name in kw_inputs:
                        is_in_kwargs = True

            if not is_in_kwargs:
                if i in pos_inputs:
                    args_list.append(pos_inputs[i])
                elif not has_var_positional:
                    # If there's no *args, we can't have gaps in positional args
                    # unless they have defaults, which bind() will handle.
                    # We can stop building the list here.
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
~~~~~

#### Acts 4: 更新 `SignatureBinder` 的调用者

`BridgedComputeService._process_request` 是调用者，需要修改它以从新的 IR 结构中提取 `args` 和 `kwargs`。

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
~~~~~

#### Acts 5: 更新 `ComputeRequest` 的规约

为了将 `args` 和 `kwargs` 从编译器传递到 VM，我们需要更新 `ComputeRequest` 的定义。

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
from ..physical.object import Ref
from ..physical.nodes import Token


@dataclass(frozen=True)
class ComputeRequest:
    code_hash: str
    input_args: List[Ref]
    input_kwargs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any]
~~~~~

#### Acts 6: 更新 `standard_launcher` 以创建新的 `ComputeRequest`

`standard_launcher` 是 `ComputeRequest` 的生产者，也需要更新。

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
~~~~~
~~~~~python.new
@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    input_args: List[Any] = []
    input_kwargs: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Iterate over all connected input ports
    for port_name, input_token in io.args.items():
        if not input_token:
            continue

        port_def = node.input_ports[port_name]

        # Update trace from every token
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.DATA:
            if port_name.isdigit():
                # This is a temporary list to build the sparse array
                idx = int(port_name)
                while len(input_args) <= idx:
                    input_args.append(None)  # Pad with placeholders
                input_args[idx] = input_token.payload
            else:
                input_kwargs[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload
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
    # Filter out any None placeholders from sparse array creation
    final_input_args = [arg for arg in input_args if arg is not None]

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=final_input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )
~~~~~

### 下一步建议

这一系列的修改是系统性的，涉及多个核心组件。在执行之后，我们需要运行完整的测试套件来验证重构的正确性，并确保没有引入回归。一旦所有测试通过，我们就可以将这个重构作为一个主要的架构改进进行提交。
