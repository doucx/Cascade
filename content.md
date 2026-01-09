好的，我分析了 `pyright` 报告的 25 个错误。这些问题都源于我们最近引入的**物理接口定义层 (PIDL)**。核心问题是静态类型检查器（Pyright）无法理解我们在元类（`PhysicsSpecMeta`）和装饰器（`@implements`）中动态定义的类型契约。

为了解决这个问题，我将执行一个计划，通过明确声明这些契约来消除所有类型错误。这不仅能让 `pyright` 通过，更重要的是，它将为我们的 Kernel 函数提供更强大的类型提示和自动补全支持。

## [WIP] fix: 补全 PIDL 类型提示以修复 Pyright 静态检查错误

### 错误分析

1.  **`PhysicsSpecMeta` 错误**: `pyright` 无法验证在元类的 `__new__` 方法中对 `cls.input_ports` 的赋值是合法的，因为它不知道 `cls`（即正在被创建的类）应该拥有这些属性。
2.  **`__spec__` 属性错误**: 在 `@implements` 装饰器中，我们向返回的 `wrapper` 函数动态附加了一个 `__spec__` 属性用于内省。`pyright` 无法静态地知道这个属性的存在。
3.  **`IO` 协议错误 (主要问题)**: 我们将 `Spec.IO` 定义为一个空的 `Protocol` 存根，并通过 `IOWrapper` 在运行时动态地提供属性（如 `ledger_in`, `req_out`）。这使得静态分析器完全无法得知 `io` 对象上有哪些可用的端口，导致了大量的 `Attribute "..." is unknown` 错误。

### 用户需求

修复所有 `pyright` 报告的类型检查错误，使代码库在静态分析层面完全合规。

### 评论

这是一个非常典型的在动态语言（Python）中引入强类型系统时遇到的问题。解决方案不是绕过类型检查，而是**拥抱它**，通过更明确的类型声明来“告知”静态分析器我们的意图。这次修复将使 PIDL 变得更加健壮和易用。

### 目标

1.  **修复 `PhysicsSpecMeta`**: 在元类中声明它将创建的类所拥有的属性。
2.  **修复 `@implements`**: 使用 `setattr` 来安全地进行动态属性赋值，向类型检查器表明这是一个有意的动态行为。
3.  **修复 `IO` 协议**: 在 `cascade-std` 的每一个 `Spec` 定义中，手动填充其内部的 `IO` 协议，明确声明所有输入和输出端口的名称和类型。

### 基本原理

*   **元类修复**: 在 `PhysicsSpecMeta` 类体中直接声明 `input_ports: Dict` 和 `output_ports: Dict`，这会告知类型系统，任何由该元类创建的类（例如 `DiscreteAllocatorSpec`）都将拥有这些类属性。
*   **装饰器修复**: 将 `wrapper.__spec__ = spec` 修改为 `setattr(wrapper, "__spec__", spec)` 是处理动态属性附加的标准实践。
*   **协议修复**: 这是本次修复的核心。我们将为每个 `Spec` 手动编写 `IO` 协议。虽然这会增加一些样板代码，但这是向静态分析器传达接口契约的最直接、最正确的方式。对于输入，我们将使用 `Optional[Token]`，因为 `IOWrapper` 的 `__getattr__` 实现返回 `dict.get()` 的结果，可能为 `None`。对于输出，我们将使用 `Token`，因为它们是必须被赋值的。

### 标签

#intent/fix #flow/ready #priority/high #comp/spec #comp/std #concept/typing #scope/dx #ai/instruct #task/domain/typing #task/object/pyright-errors #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `PhysicsSpecMeta` 和基类 `PhysicsSpec`

首先，我们修复 `cascade-spec` 中的元类定义，告知类型检查器它将创建的类上会存在 `input_ports` 和 `output_ports` 属性。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics/spec.py
~~~~~
~~~~~python.old
from typing import Dict, Protocol
from .core import PortDef, PortDirection


class PhysicsSpecMeta(type):
    def __new__(mcs, name, bases, namespace):
        # 1. Create the class
        cls = super().__new__(mcs, name, bases, namespace)

        input_ports: Dict[str, PortDef] = {}
        output_ports: Dict[str, PortDef] = {}

        # 2. Inherit ports from base classes (if any)
        # We traverse bases in reverse order so that later bases (and the class itself) override earlier ones.
        for base in reversed(bases):
            if hasattr(base, "input_ports"):
                input_ports.update(base.input_ports)
            if hasattr(base, "output_ports"):
                output_ports.update(base.output_ports)

        # 3. Collect ports from the current class definition
        for key, value in namespace.items():
            if isinstance(value, PortDef):
                # The key in the dict is the attribute name (e.g. 'ledger_in').
                # The value.name is the actual string name of the port (e.g. "ledger_in").
                # Usually they are the same, but the dict allows access by attribute name.
                if value.direction == PortDirection.INPUT:
                    input_ports[key] = value
                else:
                    output_ports[key] = value

        # 4. Register the collected ports
        cls.input_ports = input_ports
        cls.output_ports = output_ports

        return cls


class PhysicsSpec(metaclass=PhysicsSpecMeta):
    input_ports: Dict[str, PortDef]
    output_ports: Dict[str, PortDef]

    class IO(Protocol):
        """
        Protocol stub for Kernel function type hinting.

        In the future, `@implements(Spec)` will use this Protocol to enforce
        that the kernel function accepts an 'io' object with attributes matching
        the Spec's ports.
        """

        pass
~~~~~
~~~~~python.new
from typing import Dict, Protocol, ClassVar
from .core import PortDef, PortDirection


class PhysicsSpecMeta(type):
    input_ports: Dict[str, PortDef]
    output_ports: Dict[str, PortDef]

    def __new__(mcs, name, bases, namespace):
        # 1. Create the class
        cls = super().__new__(mcs, name, bases, namespace)

        input_ports: Dict[str, PortDef] = {}
        output_ports: Dict[str, PortDef] = {}

        # 2. Inherit ports from base classes (if any)
        # We traverse bases in reverse order so that later bases (and the class itself) override earlier ones.
        for base in reversed(bases):
            if hasattr(base, "input_ports"):
                input_ports.update(base.input_ports)
            if hasattr(base, "output_ports"):
                output_ports.update(base.output_ports)

        # 3. Collect ports from the current class definition
        for key, value in namespace.items():
            if isinstance(value, PortDef):
                # The key in the dict is the attribute name (e.g. 'ledger_in').
                # The value.name is the actual string name of the port (e.g. "ledger_in").
                # Usually they are the same, but the dict allows access by attribute name.
                if value.direction == PortDirection.INPUT:
                    input_ports[key] = value
                else:
                    output_ports[key] = value

        # 4. Register the collected ports
        cls.input_ports = input_ports
        cls.output_ports = output_ports

        return cls


class PhysicsSpec(metaclass=PhysicsSpecMeta):
    input_ports: ClassVar[Dict[str, PortDef]]
    output_ports: ClassVar[Dict[str, PortDef]]

    class IO(Protocol):
        """
        Protocol stub for Kernel function type hinting.

        In the future, `@implements(Spec)` will use this Protocol to enforce
        that the kernel function accepts an 'io' object with attributes matching
        the Spec's ports.
        """

        pass
~~~~~

#### Acts 2: 修复 `@implements` 装饰器

接下来，我们修复 `kernel_tools.py` 中的动态属性赋值。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/kernel_tools.py
~~~~~
~~~~~python.old
        # Attach spec metadata for introspection/docs
        wrapper.__spec__ = spec
        return wrapper
~~~~~
~~~~~python.new
        # Attach spec metadata for introspection/docs
        setattr(wrapper, "__spec__", spec)
        return wrapper
~~~~~

#### Acts 3: 填充 `cascade-std` 中的所有 `IO` 协议

现在，我们进行最核心的修复：为 `cascade-std` 中所有的 `Spec` 定义填充 `IO` 协议。

首先是资源相关的 Specs。
~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/resource.py
~~~~~
~~~~~python
from typing import Protocol, MutableMapping, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class DiscreteAllocatorSpec(PhysicsSpec):
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)

    # Dynamic Grant Outputs
    # Allows writing to 'gnt_for_{requestor_id}'
    grants = Port.MapOutput(
        prefix="gnt_for_", role=PortRole.RESOURCE, type=PortType.Token
    )

    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        ledger_in: Optional[Token]
        req_in: Optional[Token]

        # Outputs
        ledger_out: Token
        gnt_out: Token
        grants: MutableMapping[str, Token]
        req_parked: Token


class ResourceRequestorSpec(PhysicsSpec):
    amount = Port.Input("amount", role=PortRole.DATA, type="int")
    req_out = Port.Output("req_out", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        amount: Optional[Token]
        req_out: Token


class DiscreteReclaimerSpec(PhysicsSpec):
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Signal emitted to wake up parked requests
    signal_out = Port.Output("signal_out", role=PortRole.SIGNAL, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        ledger_in: Optional[Token]
        rel_in: Optional[Token]

        # Outputs
        ledger_out: Token
        signal_out: Token
~~~~~

然后是系统相关的 Specs。
~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/system.py
~~~~~
~~~~~python
from typing import Protocol, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class EgressSpec(PhysicsSpec):
    # The physical port name is "in" (reserved keyword in Python).
    # We map it to the attribute 'input_token'.
    input_token = Port.Input("in", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        input_token: Optional[Token]


class GateSpec(PhysicsSpec):
    req_in = Port.Input("req_in", role=PortRole.DATA)
    signal_in = Port.Input("signal_in", role=PortRole.SIGNAL)

    req_out = Port.Output("req_out", role=PortRole.DATA)

    class IO(Protocol):
        req_in: Optional[Token]
        signal_in: Optional[Token]

        req_out: Token


class SleepSpec(PhysicsSpec):
    delay_in = Port.Input("delay_in", role=PortRole.DATA, type="float")
    data_in = Port.Input("data_in", role=PortRole.DATA, type=PortType.Token)
    # No outputs (Void) - flow resumes via ChronosService injection

    class IO(Protocol):
        delay_in: Optional[Token]
        data_in: Optional[Token]
~~~~~

最后是核心的 Triad Specs。
~~~~~act
write_file
packages/cascade-std/src/cascade/std/specs/triad.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class BleacherSpec(PhysicsSpec):
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Conditional Execution
    condition = Port.Input("condition", role=PortRole.SIGNAL, type="Bool")
    # Startup Pulse
    pulse = Port.Input("__pulse__", role=PortRole.SIGNAL)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        # Inputs
        args: Dict[str, Token]
        condition: Optional[Token]
        pulse: Optional[Token]

        # Outputs
        worker_input: Token
        trace_output: Token
        context_output: Token
        obs_output: Token


class ObservabilitySpec(PhysicsSpec):
    event_token = Port.Input("event_token", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        event_token: Optional[Token]


class WorkerSpec(PhysicsSpec):
    # Inputs
    worker_input = Port.Input("worker_input", role=PortRole.DATA, type="Dict")

    # Outputs
    worker_result = Port.Output("worker_result", role=PortRole.DATA, type=PortType.Any)

    class IO(Protocol):
        # Inputs
        worker_input: Optional[Token]

        # Outputs
        worker_result: Token


class StainerSpec(PhysicsSpec):
    # Inputs
    worker_result = Port.Input("worker_result", role=PortRole.DATA, type=PortType.Any)
    trace_input = Port.Input("trace_input", role=PortRole.DATA, type="TraceCtx")
    context_input = Port.Input("context_input", role=PortRole.DATA, type="Dict")

    # Outputs
    output_default = Port.Output(
        "output_default", role=PortRole.DATA, type=PortType.Token
    )
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
    # Resource returns are dynamic

    class IO(Protocol):
        # Inputs
        worker_result: Optional[Token]
        trace_input: Optional[Token]
        context_input: Optional[Token]

        # Outputs
        output_default: Token
        output_error: Token
        obs_output: Token
~~~~~

### 下一步建议

我们已经完成了所有的代码修复。现在，我建议你重新运行 `pyright` 静态检查命令，以验证所有 25 个错误都已成功解决。

```bash
pyright packages/cascade-spec/ packages/cascade-reflection/ packages/cascade-compiler/ packages/cascade-std/
```

如果检查通过，我们就可以将这些修改作为一个完整的提交来固化。
