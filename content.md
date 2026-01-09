好的，我理解这个全面的实施路线图。我们的目标是完成 `cascade-std` 库向强类型物理接口定义层 (PIDL) 的完全迁移，以实现 100% 的类型安全和静态分析覆盖。

我将生成一个计划，该计划将原子化地执行您清单中的所有步骤。

## [WIP] refactor(std): 将剩余 IC 迁移到类型化的 PhysicsSpec 接口

### 用户需求

根据提供的路线图，将 `cascade-std` 库中所有剩余的使用原始字典接口的集成电路 (ICs) / Kernel 函数，全部迁移到强类型的 `PhysicsSpec` 和 `@implements` 装饰器模式。这包括：
1.  `standard_dispatcher`
2.  `standard_retry_logic`
3.  `halt_signal` 和 `drain_signal`
4.  `continuous_allocator` 和 `continuous_reclaimer`

### 评论

这是一个关键的重构，它标志着 Cascade 物理层接口规范化的完成。通过强制所有标准库 IC 遵循显式契约，我们极大地提升了系统的健壮性、可维护性和开发者体验 (DX)。这使得利用 `pyright` 等静态分析工具成为可能，从而在编码阶段就能捕获一整类潜在的运行时错误。

### 目标

1.  在 `cascade-std/src/cascade/std/specs/` 目录下为所有目标 IC 创建新的 `PhysicsSpec` 定义。
2.  使用 `@implements` 装饰器重构所有目标 Kernel 函数。
3.  将函数的实现逻辑从操作原始的 `inputs` 字典，改为操作类型安全的 `io` 对象。
4.  在所有必要的 Kernel 函数中添加 `assert` 语句，以确保输入的有效性并辅助类型推断。
5.  更新 `__init__.py` 文件以导出所有新的 `Spec` 类。

### 基本原理

此举遵循“契约先行”的设计原则。通过首先定义 `PhysicsSpec`，我们为每个 Kernel 函数建立了一个清晰、不可变的接口。`@implements` 装饰器作为一个适配器，将底层的字典式 I/O 转换为类型安全的属性访问，而无需修改 VM 的核心调用机制。这使得重构工作对 VM 透明，同时为开发者提供了现代化的、类型安全的开发范式。这最终将使整个代码库更易于理解、测试和扩展。

### 标签

#intent/refine #flow/ready #priority/high #comp/cli #concept/state #scope/api #scope/dx #ai/instruct #task/domain/pidl #task/object/std-ic-migration #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义系统和资源 IC 的新 Spec

我们首先在 `specs` 目录中创建所有必需的 `PhysicsSpec` 类。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/system.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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


class RetrySpec(PhysicsSpec):
    error_in = Port.Input("error_in", role=PortRole.DATA)
    context_in = Port.Input("context_in", role=PortRole.DATA)

    retry_out = Port.Output("retry_out", role=PortRole.DATA)
    fail_out = Port.Output("fail_out", role=PortRole.DATA)

    class IO(Protocol):
        error_in: Optional[Token]
        context_in: Optional[Token]
        retry_out: Token
        fail_out: Token


class TerminatorSpec(PhysicsSpec):
    # Typically triggerless, but can have an optional input
    trigger = Port.Input("in", role=PortRole.SIGNAL)
    out = Port.Output("out", role=PortRole.DATA)

    class IO(Protocol):
        trigger: Optional[Token]
        out: Token


class DrainerSpec(PhysicsSpec):
    trigger = Port.Input("in", role=PortRole.SIGNAL)
    out = Port.Output("out", role=PortRole.DATA)

    class IO(Protocol):
        trigger: Optional[Token]
        out: Token
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/resource.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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


class ContinuousAllocatorSpec(PhysicsSpec):
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA)

    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE)
    req_out = Port.Output(
        "req_out", role=PortRole.DATA
    )  # For failed/parked requests

    class IO(Protocol):
        ledger_in: Optional[Token]
        req_in: Optional[Token]
        ledger_out: Token
        gnt_out: Token
        req_out: Token


class ContinuousReclaimerSpec(PhysicsSpec):
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA)

    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)

    class IO(Protocol):
        ledger_in: Optional[Token]
        rel_in: Optional[Token]
        ledger_out: Token
~~~~~

#### Acts 2: 导出新的 Spec

现在，我们将这些新的 Spec 添加到 `__init__.py` 文件中，使其在整个库中可用。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/__init__.py
~~~~~
~~~~~python.old
from .resource import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
)
from .triad import BleacherSpec, WorkerSpec, StainerSpec, ObservabilitySpec
from .system import EgressSpec, GateSpec, SleepSpec

__all__ = [
    "DiscreteAllocatorSpec",
    "DiscreteReclaimerSpec",
    "BleacherSpec",
    "ObservabilitySpec",
    "WorkerSpec",
    "StainerSpec",
    "EgressSpec",
    "GateSpec",
    "SleepSpec",
    "ResourceRequestorSpec",
]
~~~~~
~~~~~python.new
from .resource import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    ContinuousAllocatorSpec,
    ContinuousReclaimerSpec,
)
from .triad import BleacherSpec, WorkerSpec, StainerSpec, ObservabilitySpec
from .system import (
    EgressSpec,
    GateSpec,
    SleepSpec,
    RetrySpec,
    TerminatorSpec,
    DrainerSpec,
)

__all__ = [
    "DiscreteAllocatorSpec",
    "DiscreteReclaimerSpec",
    "BleacherSpec",
    "ObservabilitySpec",
    "WorkerSpec",
    "StainerSpec",
    "EgressSpec",
    "GateSpec",
    "SleepSpec",
    "ResourceRequestorSpec",
    "ContinuousAllocatorSpec",
    "ContinuousReclaimerSpec",
    "RetrySpec",
    "TerminatorSpec",
    "DrainerSpec",
]
~~~~~

#### Acts 3: 重构 ICs 以实现新的 Spec

最后，我们将逐一重构目标 IC 函数，应用新的 Spec。

##### A. Triad IC (Dispatcher)

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python.old
import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import WorkerNode
from cascade.spec.physical.object import Ref
from cascade.vm.compute import ComputeRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_dispatcher(
    inputs: Dict[str, Token], node: WorkerNode, resources: Any
) -> Dict[str, Token]:
    # 1. Extract input refs from the token prepared by the Bleacher.
    # The payload of the 'worker_input' token is expected to be a Dict[str, Ref].
    worker_input_token = inputs["worker_input"]
    input_refs: Dict[str, Ref] = worker_input_token.payload

    # 2. Deterministically calculate the reply-to address (the downstream DataNode).
    base_id = node.id.replace(".worker", "")
    reply_to_nid = PhysicalIdGenerator.worker_out_data(base_id)

    # 3. Get the code hash from the node's metadata.
    code_hash = node.canonical_code_structure_hash
    if not code_hash:
        raise ValueError(
            f"WorkerNode '{node.id}' is missing canonical_code_structure_hash. "
            "The compiler must populate this field."
        )

    # 4. Propagate the trace from the input token.
    trace = worker_input_token.trace

    # 5. Assemble the computation request.
    request = ComputeRequest(
        code_hash=code_hash,
        input_refs=input_refs,
        reply_to_nid=reply_to_nid,
        trace=trace,
    )

    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error(
            "Resource 'system.compute_queue' not found. Cannot dispatch compute request."
        )
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise

    # 7. Return an empty dictionary to "evaporate" the energy in this branch.
    # The flow will resume when the ComputeService places the result token
    # into the `reply_to_nid` data node.
    return {}
~~~~~
~~~~~python.new
import logging
from typing import Any, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.triad import WorkerNode
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.compute import ComputeRequest
from cascade.std.specs import WorkerSpec
from cascade.std.kernel_tools import implements

logger = logging.getLogger(__name__)


@implements(WorkerSpec)
def standard_dispatcher(io: WorkerSpec.IO, node: WorkerNode, resources: Any) -> None:
    # 1. Extract input refs from the token prepared by the Bleacher.
    # The payload of the 'worker_input' token is expected to be a Dict[str, Ref].
    worker_input_token = io.worker_input
    assert worker_input_token is not None, "Worker input token is missing"
    input_refs: Dict[str, Ref] = worker_input_token.payload

    # 2. Deterministically calculate the reply-to address (the downstream DataNode).
    base_id = node.id.replace(".worker", "")
    reply_to_nid = PhysicalIdGenerator.worker_out_data(base_id)

    # 3. Get the code hash from the node's metadata.
    code_hash = node.canonical_code_structure_hash
    if not code_hash:
        raise ValueError(
            f"WorkerNode '{node.id}' is missing canonical_code_structure_hash. "
            "The compiler must populate this field."
        )

    # 4. Propagate the trace from the input token.
    trace = worker_input_token.trace

    # 5. Assemble the computation request.
    request = ComputeRequest(
        code_hash=code_hash,
        input_refs=input_refs,
        reply_to_nid=reply_to_nid,
        trace=trace,
    )

    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error(
            "Resource 'system.compute_queue' not found. Cannot dispatch compute request."
        )
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise

    # 7. Return nothing to "evaporate" the energy in this branch.
    # The flow will resume when the ComputeService places the result token
    # into the `reply_to_nid` data node.
    # The @implements decorator handles returning the empty output dict.
~~~~~

##### B. System Control ICs

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/retry.py
~~~~~
~~~~~python.old
from typing import Dict, Any

from cascade.spec import RetryNode
from cascade.spec.physical.nodes import Token


def standard_retry_logic(
    inputs: Dict[str, Token], node: RetryNode, resources: Any
) -> Dict[str, Token]:
    error_token = inputs["error_in"]
    context_token = inputs["context_in"]

    # State is in the token trace
    trace = context_token.trace
    retry_count = trace.get("retry_count", 0)
    retry_count += 1

    # Policy is in the node definition
    max_attempts = node.max_attempts

    if retry_count < max_attempts:
        # Retry: update state and route context token back
        trace["retry_count"] = retry_count
        return {"retry_out": context_token}
    else:
        # Fail permanently: route error token to the failure output port
        return {"fail_out": error_token}
~~~~~
~~~~~python.new
from typing import Any

from cascade.spec import RetryNode
from cascade.std.specs import RetrySpec
from cascade.std.kernel_tools import implements


@implements(RetrySpec)
def standard_retry_logic(io: RetrySpec.IO, node: RetryNode, resources: Any) -> None:
    error_token = io.error_in
    context_token = io.context_in

    assert context_token is not None, "Context token for retry is missing"
    assert error_token is not None, "Error token for retry is missing"

    # State is in the token trace
    trace = context_token.trace
    retry_count = trace.get("retry_count", 0)
    retry_count += 1

    # Policy is in the node definition
    max_attempts = node.max_attempts

    if retry_count < max_attempts:
        # Retry: update state and route context token back
        trace["retry_count"] = retry_count
        io.retry_out = context_token
    else:
        # Fail permanently: route error token to the failure output port
        io.fail_out = error_token
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand


def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command=ControlCommand.HALT)
    return {"out": Token(payload=control_token)}
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import TerminatorSpec
from cascade.std.kernel_tools import implements


@implements(TerminatorSpec)
def halt_signal(io: TerminatorSpec.IO, node: PhysicsNode, resources: Any) -> None:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command=ControlCommand.HALT)
    io.out = Token(payload=control_token)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand


def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command=ControlCommand.DRAIN)
    return {"out": Token(payload=control_token)}
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import DrainerSpec
from cascade.std.kernel_tools import implements


@implements(DrainerSpec)
def drain_signal(io: DrainerSpec.IO, node: PhysicsNode, resources: Any) -> None:
    control_token = SystemControlToken(command=ControlCommand.DRAIN)
    io.out = Token(payload=control_token)
~~~~~
