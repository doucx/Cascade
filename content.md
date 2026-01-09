简要回答
我们将更新 `BleacherSpec` 和 `DiscreteAllocatorSpec` 以引入动态端口映射，并使用 `@implements` 装饰器重构相应的 Kernel 函数，使其通过强类型的 `io` 接口与物理层交互。

## [WIP] feat: 实施 PIDL 阶段三 - 重构 Bleacher 与 Resource Kernels

### 用户需求
1.  修改 `BleacherSpec`，添加 `Port.MapInput` 以支持动态参数输入。
2.  修改 `DiscreteAllocatorSpec`，添加 `Port.MapOutput` 以支持动态资源授权输出。
3.  重构 `standard_bleacher` Kernel，使用 `io.args` 处理输入。
4.  重构 `discrete_allocator` 和 `discrete_reclaimer` Kernel，使用 `io.grants` 和静态属性处理资源逻辑。

### 评论
这是 PIDL 实施的关键战役。`Bleacher` 和 `Allocator` 是系统中动态性最强的两个组件。成功重构它们意味着我们的“静态优先，动态兜底”策略（PIDL + IOWrapper）能够覆盖 Cascade 中最复杂的场景，为全面推广铺平道路。

### 目标
1.  更新 `packages/cascade-std/src/cascade/std/specs/triad.py`。
2.  更新 `packages/cascade-std/src/cascade/std/specs/resource.py`。
3.  重构 `packages/cascade-std/src/cascade/std/triad/bleacher.py`。
4.  重构 `packages/cascade-std/src/cascade/std/resource/discrete.py`。

### 基本原理
*   **Bleacher 重构**: `Bleacher` 的核心职责是将杂乱的输入（数据、资源、信号）清洗为纯净的 Worker Input。通过 `io.args`，我们能获取所有非静态定义的输入 Token，然后结合 `node.input_ports` 元数据进行分类处理。这保持了逻辑的灵活性，同时规范了接口访问。
*   **Allocator 重构**: 利用 `Port.MapOutput(prefix="gnt_for_")`，我们在 Spec 层面显式声明了“动态授权”的存在。Kernel 代码使用 `io.grants["gnt_for_x"] = token` 进行赋值，`IOWrapper` 会自动校验前缀，从而增强了安全性。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #comp/interfaces #concept/spec #scope/core #ai/instruct #task/domain/core #task/object/kernel-refactor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 Triad Specs

为 `BleacherSpec` 添加动态输入映射。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/triad.py
~~~~~
~~~~~python.old
class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
~~~~~
~~~~~python.new
class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
~~~~~

#### Acts 2: 更新 Resource Specs

为 `DiscreteAllocatorSpec` 添加动态输出映射。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/resource.py
~~~~~
~~~~~python.old
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)
    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)
~~~~~
~~~~~python.new
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)
    
    # Dynamic Grant Outputs
    # Allows writing to 'gnt_for_{requestor_id}'
    grants = Port.MapOutput(prefix="gnt_for_", role=PortRole.RESOURCE, type=PortType.Token)

    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)
~~~~~

#### Acts 3: 重构 Bleacher Kernel

使用 `@implements(BleacherSpec)` 和 `io.args` 重构 `standard_bleacher`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
from cascade.spec.physical.ports import PortRole


def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode, resources: Any
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a GNT token.
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    start_ts = time.time()  # Use wall clock for IR
    mono_ts = time.monotonic()  # Use monotonic for internal duration calc

    logical_id = node.id.replace(".bleach", "")

    # Heuristic: Extract task_name from physical name "Bleach(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Bleach(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }

    # 4. Create the output tokens
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    # The context payload IS the worker payload (the input refs)
    context_token = Token(payload=worker_payload, trace=trace_payload)
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "context_output": context_token,
        "obs_output": obs_token,
    }
~~~~~
~~~~~python.new
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
from cascade.spec.physical.ports import PortRole
from cascade.std.specs import BleacherSpec
from cascade.std.kernel_tools import implements


@implements(BleacherSpec)
def standard_bleacher(
    io: BleacherSpec.IO, node: BleachNode, resources: Any
) -> None:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    # Use io.args to get all dynamic inputs
    for port_name, input_token in io.args.items():
        # Even though we use IO wrapper, we still rely on Node metadata for roles
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a GNT token.
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    start_ts = time.time()  # Use wall clock for IR
    mono_ts = time.monotonic()  # Use monotonic for internal duration calc

    logical_id = node.id.replace(".bleach", "")

    # Heuristic: Extract task_name from physical name "Bleach(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Bleach(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }

    # 4. Create the output tokens
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    # The context payload IS the worker payload (the input refs)
    context_token = Token(payload=worker_payload, trace=trace_payload)
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    # 5. Set outputs via IO wrapper
    io.worker_input = worker_token
    io.trace_output = trace_token
    io.context_output = context_token
    io.obs_output = obs_token
~~~~~

#### Acts 4: 重构 Discrete Resource Kernels

使用 `@implements(DiscreteAllocatorSpec)` 和 `@implements(DiscreteReclaimerSpec)` 重构 `discrete.py`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.spec.physical.ports import PortName


@dataclass
class DiscreteLedger:
    total: int
    available: int


def _extract_scalar(payload: Any) -> Union[int, float]:
    if isinstance(payload, Ref):
        # v3.1: Try to get hoisted scalar
        if "scalar_value" in payload.meta:
            return payload.meta["scalar_value"]
        # If not hoisted, we technically can't read it in Kernel.
        # But for now we fail gracefully or return 0?
        # Raising error is better to catch missing hoisting.
        raise ValueError(
            f"Ref {payload.uri} missing 'scalar_value' metadata for Kernel access."
        )
    return payload


def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = int(_extract_scalar(req_token.payload))

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        outputs[PortName.REQ_PARKED] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    outputs = {"ledger_out": Token(payload=ledger)}
    # Emit wake-up signal
    outputs[PortName.SIGNAL_OUT] = Token(payload=None, trace=rel_token.trace)

    return outputs
~~~~~
~~~~~python.new
from typing import Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec
from cascade.std.kernel_tools import implements


@dataclass
class DiscreteLedger:
    total: int
    available: int


def _extract_scalar(payload: Any) -> Union[int, float]:
    if isinstance(payload, Ref):
        # v3.1: Try to get hoisted scalar
        if "scalar_value" in payload.meta:
            return payload.meta["scalar_value"]
        # If not hoisted, we technically can't read it in Kernel.
        # But for now we fail gracefully or return 0?
        # Raising error is better to catch missing hoisting.
        raise ValueError(
            f"Ref {payload.uri} missing 'scalar_value' metadata for Kernel access."
        )
    return payload


@implements(DiscreteAllocatorSpec)
def discrete_allocator(
    io: DiscreteAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = io.req_in
    req_amount = int(_extract_scalar(req_token.payload))

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            # Use dynamic output map
            io.grants[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        io.req_parked = req_token

    io.ledger_out = Token(payload=ledger)


@implements(DiscreteReclaimerSpec)
def discrete_reclaimer(
    io: DiscreteReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = io.rel_in
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)
    # Emit wake-up signal
    io.signal_out = Token(payload=None, trace=rel_token.trace)
~~~~~

### 下一步建议
我们已经完成了核心 Kernel 的重构。请运行测试以验证修改是否正确。

接下来的 **阶段四：Compiler 连线重构 (The Wiring)** 将利用我们定义的 Specs 来消除 Compiler 中的硬编码字符串。具体来说，我们将修改 `cascade.compiler.backend.wiring.policies` 中的逻辑，使其引用 `Spec.port.name` 而不是字面量。这将闭合 PIDL 的环路。
