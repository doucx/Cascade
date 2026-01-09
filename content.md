简要回答
我们将创建 `@implements` 装饰器，并使用它重构 `standard_egress` 和 `gate_passthrough` 函数，使其通过 `Spec.IO` 接口访问数据，从而验证 PIDL 在实现层的可行性。

## [WIP] feat: 实施 PIDL 阶段三 - Kernel 实现重构试点

### 用户需求
验证 PIDL 在 Kernel 实现层的应用。具体任务：
1.  在 `cascade.std` 中创建一个工具模块，提供 `@implements` 装饰器和 `IO` 包装器。
2.  重构 `gate.py` 中的 `gate_passthrough` 函数，使其遵循 `GateSpec`。
3.  重构 `egress.py` 中的 `standard_egress` 函数，使其遵循 `EgressSpec`。
4.  确保现有测试通过。

### 评论
这是“物理法则”与“物理实体”的第一次接触。我们的目标是引入强类型接口而不牺牲运行时性能。通过引入一个轻量级的 `IO` 代理对象，我们可以让 Kernel 函数的代码看起来像是在操作属性（`io.req_in`），而底层实际上是在高效地访问字典（`inputs["req_in"]`）。

### 目标
1.  创建 `packages/cascade-std/src/cascade/std/kernel_tools.py`。
2.  修改 `gate.py` 和 `egress.py` 以使用新的模式。

### 基本原理
*   **`@implements(Spec)`**: 这个装饰器将负责在运行时将传统的 `(inputs, node, resources)` 签名适配为新的 `(io, node, resources)` 签名。
*   **Zero-Copy IO Wrapper**: 为了性能，`IO` 对象不会复制数据。它只是 `inputs` 字典的一个视图。
    *   `getattr(io, "req_in")` -> `inputs["req_in"]`
    *   `setattr(io, "req_out", val)` -> `outputs["req_out"] = val`
*   **向后兼容**: 在这个过渡阶段，我们保持装饰器的逻辑尽可能简单，确保它能无缝替换现有的字典操作代码，同时为未来的静态检查打下基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #concept/spec #scope/core #ai/instruct #task/domain/core #task/object/kernel #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 Kernel 工具模块

我们首先实现基础设施：`@implements` 装饰器和一个基于 `__slots__` 的高性能 `IO` 代理。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/kernel_tools.py
~~~~~
~~~~~python
from functools import wraps
from typing import Dict, Any, Type, TypeVar
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physics import PhysicsSpec

T = TypeVar("T", bound=PhysicsSpec)


class IOWrapper:
    """
    A zero-copy view over the input and output dictionaries.
    Translates attribute access to dictionary lookups based on the Spec.
    """
    __slots__ = ("_inputs", "_outputs", "_spec")

    def __init__(self, inputs: Dict[str, Token], outputs: Dict[str, Token], spec: Type[PhysicsSpec]):
        self._inputs = inputs
        self._outputs = outputs
        self._spec = spec

    def __getattr__(self, name: str) -> Any:
        # 1. Check Input Ports
        if name in self._spec.input_ports:
            port_name = self._spec.input_ports[name].name
            # If the port is not in inputs, it means no token arrived (optional input).
            # We return None in that case, or raise? For now, None seems safer for "Gate" logic.
            return self._inputs.get(port_name)
        
        # 2. Check Output Ports (for reading back what we wrote? Uncommon but possible)
        if name in self._spec.output_ports:
             port_name = self._spec.output_ports[name].name
             return self._outputs.get(port_name)

        raise AttributeError(f"'{self._spec.__name__}' IO has no port mapping for '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inputs", "_outputs", "_spec"):
            super().__setattr__(name, value)
            return

        # Check Output Ports
        if name in self._spec.output_ports:
            port_name = self._spec.output_ports[name].name
            self._outputs[port_name] = value
            return

        raise AttributeError(f"'{self._spec.__name__}' IO has no output port mapping for '{name}'")


def implements(spec: Type[PhysicsSpec]):
    """
    Decorator that adapts a kernel function to use the typed IO interface.
    
    Transforms:
        def my_kernel(inputs, node, resources) -> Dict
    Into:
        def my_kernel(io, node, resources) -> None
        
    The wrapper handles the creation of the outputs dictionary and returns it.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(inputs: Dict[str, Token], node: PhysicsNode, resources: Any) -> Dict[str, Token]:
            outputs: Dict[str, Token] = {}
            io = IOWrapper(inputs, outputs, spec)
            
            # Call the inner function. It is expected to set attributes on 'io' (populating 'outputs')
            # and return None.
            func(io, node, resources)
            
            return outputs
        
        # Attach spec metadata for introspection/docs
        wrapper.__spec__ = spec
        return wrapper
    return decorator
~~~~~

#### Acts 2: 重构 Gate Kernel

修改 `gate.py`，使用 `GateSpec` 和 `@implements`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/gate.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def gate_passthrough(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # We expect 'req_in' and 'signal_in' ports
    req_token = inputs.get("req_in")
    signal_token = inputs.get("signal_in")

    if req_token and signal_token:
        # The gate is open, pass the request token through
        return {"req_out": req_token}

    # Should not happen if wired correctly, but return empty if not fully triggered
    return {}
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import GateSpec
from cascade.std.kernel_tools import implements


@implements(GateSpec)
def gate_passthrough(
    io: GateSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    # Access inputs via Spec-defined attributes
    # The IO wrapper maps 'io.req_in' -> inputs["req_in"]
    if io.req_in and io.signal_in:
        # The gate is open, pass the request token through
        # The IO wrapper maps 'io.req_out' -> outputs["req_out"]
        io.req_out = io.req_in
~~~~~

#### Acts 3: 重构 Egress Kernel

修改 `egress.py`，使用 `EgressSpec` 和 `@implements`。注意这里的输入端口映射：`input_token` (Spec属性) -> `"in"` (物理端口名)。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/egress.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def standard_egress(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Get the Egress Queue from system resources
    # This must be registered by the Strategy during startup.
    queue = resources.get("system.egress_queue")

    # 2. Consume the token
    # Phase 3.3 of the roadmap defines the input port as 'in'.
    token = inputs.get("in")

    if token:
        # 3. Export
        # We wrap the token with the node ID so the Strategy knows which egress node it came from.
        # This allows handling multiple egress points (e.g. for different task results).
        queue.put_nowait((node.id, token))

    # 4. Return empty (Evaporate)
    # No tokens are returned to the graph. The energy leaves the system here.
    return {}
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import EgressSpec
from cascade.std.kernel_tools import implements


@implements(EgressSpec)
def standard_egress(
    io: EgressSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    # 1. Get the Egress Queue
    queue = resources.get("system.egress_queue")

    # 2. Consume the token
    # Spec mapping: io.input_token -> inputs["in"]
    token = io.input_token

    if token:
        # 3. Export
        queue.put_nowait((node.id, token))
    
    # 4. Return empty (Evaporate)
    # Implicitly returns the empty 'outputs' dict created by @implements
~~~~~

### 下一步建议
我们已经成功重构了两个简单的 Kernel。接下来，我建议运行测试以确保我们没有破坏任何东西。如果一切正常，我们可以继续重构更复杂的 `DiscreteAllocator` 和 `Bleacher`。

特别注意：`Bleacher` 的重构会比较复杂，因为它的输入端口是动态的，而 Spec 目前主要关注静态契约。我们可能需要扩展 `IOWrapper` 来支持动态属性访问，或者在 `Bleacher` 中混合使用 `io` 和原始 `inputs`（虽然我们应尽量避免混合）。对于 `DiscreteAllocator`，挑战在于处理动态的 `gnt_for_X` 输出端口。

请确认是否运行测试。
