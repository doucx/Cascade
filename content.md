好的，我们开始实施 **第四阶段：标准库同步化 (Phase 4: StdLib Synchronization)**。

此阶段的目标是重写 `cascade-std` 中的核心“三连体”组件（Bleacher, Stainer, Observer），使它们从 `async` 协程转变为纯同步函数，并使其逻辑与新的 Ref-Based 模型对齐。

## [WIP] feat(std): 同步化标准库 Triad 并适配 Ref 模型

### 用户需求
重写 `cascade.std.triad` 中的 `standard_bleacher`、`standard_stainer` 和 `standard_observer`，移除所有 `async` 关键字，并更新 `stainer` 的逻辑以处理 `Ref` 元数据。

### 评论
这是将 v3.1 架构理论落地到具体执行逻辑的关键一步。通过将这些核心 ICs（集成电路）同步化，我们确保了 `PhysicsKernel` 的执行循环中不存在任何 `await`，从而为物理层的微秒级性能奠定了基础。`Stainer` 的改造尤其重要，它将路由决策的依据从检查实际数据转移到了检查轻量级的 `Ref.meta`，这是实现“控制与数据分离”的核心体现。

### 目标
1.  将 `standard_bleacher` 修改为同步函数。
2.  将 `standard_stainer` 修改为同步函数，并使其路由逻辑基于 `Ref.meta['is_error']`。
3.  将 `standard_observer` 修改为同步函数。

### 基本原理
*   **同步化**: 简单地将 `async def` 替换为 `def`。所有被调用的子系统（如 `EventBus`）必须支持从同步上下文中进行非阻塞调用。
*   **Stainer 逻辑**:
    *   **输入**: `stainer` 从 `worker_result` 端口接收的 `Token`，其载荷（payload）现在是一个 `Ref` 对象。
    *   **决策**: 通过检查 `ref.meta.get('is_error', False)` 来判断上一步计算是否成功。
    *   **输出**: 根据决策结果，将包含原始 `Ref` 的 `Token` 放入返回字典中，键名为 `output_default` 或 `output_error`，这与 `StainNode` 的“主权端口”定义相匹配。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/kernel #scope/core #ai/instruct #task/domain/stdlib #task/object/triad-functions #task/action/synchronize #task/state/continue

---

### Script

#### Acts 1: 同步化 `standard_bleacher`

`bleacher` 的逻辑主要是传递载荷和创建元数据，其核心结构不受 `Ref` 模型影响，只需移除 `async`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState
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
    ctx = {}
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
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }
~~~~~

#### Acts 2: 改造 `standard_stainer`

这是核心修改。`stainer` 现在检查 `Ref` 的元数据来决定路由，并通过不同的输出端口（`output_default`/`output_error`）发送结果。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python
from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import StainNode
from cascade.spec.physical.ports import PortRole


def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_mono = time.monotonic()
    now_wall = time.time()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_ref = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # --- Ref-Based Logic ---
    # The result_ref is expected to be a Ref object.
    # We decide state based on its metadata, not its payload.
    state = EventState.SUCCEEDED
    error_msg = None
    output_port = "output_default"
    result_preview = None

    if isinstance(result_ref, Ref):
        is_error = result_ref.meta.get("is_error", False)
        if is_error:
            state = EventState.FAILED
            # The actual error object is in the remote store,
            # we can only preview what's in the meta.
            error_msg = result_ref.meta.get("error_str", "Error flag set in Ref meta")
            output_port = "output_error"
        else:
             result_preview = result_ref.meta.get("preview", str(result_ref))
    elif isinstance(result_ref, Exception):
        # Fallback for systems where an exception might still be passed directly
        state = EventState.FAILED
        error_msg = str(result_ref)
        output_port = "output_error"

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": task_name,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": result_preview,
        },
    }

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result (routed via sovereign port)
    outputs[output_port] = Token(payload=result_ref, trace=trace_payload)

    # 4.2 Observability Event
    outputs["obs_output"] = Token(payload=ir, trace=trace_payload)

    # 4.3 Resource Return
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            amount = 1
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]
            outputs[port_name] = Token(payload=amount)

    return outputs
~~~~~

#### Acts 3: 同步化 `standard_observer`

`observer` 的逻辑非常简单，只需移除 `async`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.spec import EventIR
from cascade.spec.physical.nodes import Token, PhysicsNode


def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The Observer is now a "Dumb Relay".
    # It blindly forwards the IR payload to the system EventBus.

    # 1. Get the EventBus from resources
    # This must be injected by the runtime/harness.
    bus = resources.get("system.event_bus")

    # 2. Extract IR
    token = inputs["event_token"]
    ir: EventIR = token.payload

    # 3. Publish
    if bus and ir:
        # We assume the bus supports a non-blocking publish from sync code.
        bus.publish_ir(ir)

    # Observers do not return tokens into the graph
    return {}
~~~~~

### 下一步建议
我们已经成功地将标准库的核心 ICs 转换为同步、Ref-aware 的形式。现在，物理内核（`PhysicsKernel`）已经拥有了可以执行的“标准固件”。

下一步是 **第五阶段：反应堆进化 (Phase 5: Reactor Evolution)**。我们需要改造 `Reactor`，使其能够：
1.  区分 `KernelNode` 和 `UserNode`。
2.  使用 `PhysicsKernel` 同步执行前者。
3.  使用 `ComputeDelegate` 异步提交后者，并实现“断连式异步桥接”来回收结果。

这将是整个架构的最后一块拼图。
