## [WIP] feat(dyad): 定义二元体物理契约与标准 IC 实现

### 用户需求
基于 ADAP v1.0 协议的分析结果，我们需要构建支持“确定性数据流”的 Dyad (二元体) 架构基础组件。
具体需求包括：
1.  **定义物理节点契约**: 创建 `LauncherNode` 和 `LanderNode` 的物理定义。特别地，`LauncherNode` 必须包含 `reply_to_nid` 字段，以消除对拓扑结构的隐式猜测。
2.  **定义 IO 规范**: 创建 `LauncherSpec` 和 `LanderSpec`，定义这两个新组件的端口界面。
3.  **实现标准 IC**: 编写 `standard_launcher` 和 `standard_lander` 的 Python 实现。`standard_launcher` 必须利用 `reply_to_nid` 来确定结果回传地址。

### 评论
这是对系统核心执行模型的一次重大升级。通过在 `LauncherNode` 中显式编码 `reply_to_nid`，我们不仅消除了竞态条件，还解耦了 IC 逻辑与图拓扑生成逻辑。IC 不再需要知道“我的下游节点通常叫什么名字”，它只需要知道“我的配置告诉我把结果发到哪里”。这显著增强了系统的健壮性和可测试性。

### 目标
1.  在 `cascade-spec` 中创建 `physical/dyad.py` 和 `specs/dyad.py`。
2.  在 `cascade-std` 中创建 `dyad/launcher.py` 和 `dyad/lander.py`。
3.  确保 `standard_launcher` 正确处理 Trace 上下文的合并与透传。
4.  确保 `standard_lander` 正确从 Trace 中恢复时间戳并计算耗时。

### 基本原理
1.  **物理节点定义**: `LauncherNode` 继承自 `PhysicsFuncNode`，并增加 `canonical_code_structure_hash` (执行什么) 和 `reply_to_nid` (结果去哪) 两个关键字段。
2.  **IO 规范**:
    *   `LauncherSpec`: 类似于旧的 `Bleacher`，但没有数据输出端口（数据走隧道）。
    *   `LanderSpec`: 类似于旧的 `Stainer`，但没有独立的 `trace` 输入端口（Trace 走隧道）。
3.  **IC 实现**:
    *   `Launcher`: 负责参数聚合、Trace 初始化、以及通过 Compute Service 发射任务。
    *   `Lander`: 负责接收结果、Trace 恢复、生命周期事件发射以及资源归还。

### 标签
#intent/architect #intent/build #flow/ready #priority/high
#comp/spec #comp/std #scope/core
#task/domain/architecture #task/object/dyad-components #task/action/implementation
#task/state/continue

---

### Script

#### Acts 1: 定义物理节点 (Physical Nodes)

我们在 `cascade-spec` 中定义新的物理节点类型。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physical/dyad.py
~~~~~
~~~~~python
from dataclasses import dataclass
from .nodes import PhysicsFuncNode


@dataclass
class LauncherNode(PhysicsFuncNode):
    """
    The Launcher is the first half of the Dyad.
    It prepares the context, aggregates arguments, and dispatches the compute request.
    """
    # The canonical hash of the code to be executed.
    canonical_code_structure_hash: str = ""
    
    # The explicit ID of the DataNode where the result should be deposited.
    # This eliminates the need for topological guessing.
    reply_to_nid: str = ""


@dataclass
class LanderNode(PhysicsFuncNode):
    """
    The Lander is the second half of the Dyad.
    It receives the result, finalizes the lifecycle, and handles routing.
    """
    pass
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physical/__init__.py
~~~~~
~~~~~python.new
from .triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
    RetryNode,
)
from .dyad import (
    LauncherNode,
    LanderNode,
)
~~~~~

#### Acts 2: 定义组件规范 (Component Specs)

我们在 `cascade-spec` 中定义 IO 规范。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/specs/dyad.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Optional, MutableMapping
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class LauncherSpec(PhysicsSpec):
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Conditional Execution
    condition = Port.Input("condition", role=PortRole.SIGNAL, type="Bool")
    # Startup Pulse
    pulse = Port.Input("__pulse__", role=PortRole.SIGNAL)

    # Outputs
    # Note: No DATA output. The Compute Request is sent via the System Bus (Tunnel).
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        # Inputs
        args: Dict[str, Token]
        condition: Optional[Token]
        pulse: Optional[Token]

        # Outputs
        obs_output: Token


class LanderSpec(PhysicsSpec):
    # Inputs
    # The result arrives via this port from the D_result node.
    result_token = Port.Input("result_token", role=PortRole.DATA, type=PortType.Any)

    # Outputs
    output_default = Port.Output(
        "output_default", role=PortRole.DATA, type=PortType.Token
    )
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
    
    # Resource returns are dynamic
    resource_returns = Port.MapOutput(role=PortRole.RESOURCE, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        result_token: Optional[Token]

        # Outputs
        output_default: Token
        output_error: Token
        obs_output: Token
        resource_returns: MutableMapping[str, Token]
~~~~~

#### Acts 3: 实现 Launcher IC

在 `cascade-std` 中实现 `standard_launcher`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-std/src/cascade/std/dyad
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/dyad/launcher.py
~~~~~
~~~~~python
from typing import Any, Dict, List
import time
import logging

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.dyad import LauncherNode
from cascade.spec.physical.ports import PortRole
from cascade.spec.physical.object import Ref
from cascade.spec.specs.dyad import LauncherSpec
from cascade.spec.physics.binding import implements
from cascade.spec.runtime import ComputeRequest

logger = logging.getLogger(__name__)


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
    mono_ts = time.monotonic() # Monotonic for internal duration

    # Extract logical ID and Task Name
    # Convention: logical_id is the prefix of the physical ID
    logical_id = node.id.split(".")[0]
    
    task_name = "unknown"
    if node.name.startswith("Launch(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    # Update Trace
    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (STARTED)
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

    # 4. Emit Observability Event
    # The Launcher emits the STARTED event directly.
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Dispatch Compute Request
    if not node.reply_to_nid:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'reply_to_nid'. "
            "Determinism violation: Cannot dispatch without explicit return address."
        )

    if not node.canonical_code_structure_hash:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'canonical_code_structure_hash'."
        )

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_refs=input_refs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload  # Trace Tunneling happens here
    )

    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error("Resource 'system.compute_queue' not found.")
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise
~~~~~

#### Acts 4: 实现 Lander IC

在 `cascade-std` 中实现 `standard_lander`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/dyad/lander.py
~~~~~
~~~~~python
from typing import Any, Dict
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.dyad import LanderNode
from cascade.spec.specs.dyad import LanderSpec
from cascade.spec.physics.binding import implements


@implements(LanderSpec)
def standard_lander(io: LanderSpec.IO, node: LanderNode, resources: Any) -> None:
    end_mono = time.monotonic()
    now_wall = time.time()

    # 1. Extract Result & Recover Trace
    result_token = io.result_token
    if not result_token:
        # Should technically not happen if activated, but safety first
        return

    result_payload = result_token.payload
    trace_payload = result_token.trace.copy()  # Recovered from Tunnel

    # 2. Calculate Duration
    # The start_ts was injected by the Launcher into the trace
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR (FINISHED)
    logical_id = node.id.split(".")[0]
    
    task_name = "unknown"
    if node.name.startswith("Land(") and node.name.endswith(")"):
        task_name = node.name[5:-1]

    # Determine Status
    state = EventState.SUCCEEDED
    error_msg = None

    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Preview Logic
    preview = None
    if state == EventState.SUCCEEDED:
        # Check for Ref-like object by duck typing or explicit import
        # For simplicity in stdlib, we just str() it if not explicit Ref check
        # Ideally we check against cascade.spec.physical.object.Ref
        if hasattr(result_payload, "uri") and hasattr(result_payload, "meta"):
             preview = result_payload
        else:
             preview = str(result_payload)[:100]

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
            "result_preview": preview,
        },
    }

    # 4. Emit Observability Event
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Routing (Default vs Error)
    if state == EventState.FAILED and "output_error" in node.output_ports:
        io.output_error = Token(payload=result_payload, trace=trace_payload)
    else:
        io.output_default = Token(payload=result_payload, trace=trace_payload)

    # 6. Resource Return
    # We iterate over the dynamic resource return ports defined on the Node
    # and match them against what we claimed in the trace.
    resource_amounts = trace_payload.get("resource_amounts", {})
    
    # We can't iterate io.resource_returns directly as it's an output map.
    # We must look at the Node's output ports definition.
    for port_name in node.output_ports:
        # The Spec defines resource returns as a map, so physical ports will have names.
        # We need a way to identify which ports are resource returns.
        # The Spec defines them with role=RESOURCE.
        port_def = node.output_ports[port_name]
        if port_def.role == "RESOURCE": # String match or import PortRole
            # Found a resource return port
            amount = resource_amounts.get(port_name, 1) # Default to 1 if not tracked
            io.resource_returns[port_name] = Token(payload=amount)
~~~~~

#### Acts 5: 导出新组件

更新 `__init__.py`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/__init__.py
~~~~~
~~~~~python
# Standard library of physical primitives (ICs) for the Cascade VM.

from .dyad.launcher import standard_launcher
from .dyad.lander import standard_lander

# Legacy Triad (Keep for backward compatibility until full migration)
from .triad.dispatcher import standard_dispatcher
from .triad.bleacher import standard_bleacher
from .triad.stainer import standard_stainer
from .triad.observer import standard_observer

# System
from .system.gate import gate_passthrough
from .system.retry import standard_retry_logic
from .system.time import standard_sleep
from .system.egress import standard_egress
from .system.drainer import drain_signal
from .system.terminator import halt_signal

# Resource
from .resource.requestor import resource_requestor
from .resource.discrete import discrete_allocator, discrete_reclaimer
from .resource.continuous import continuous_allocator, continuous_reclaimer

__all__ = [
    "standard_launcher",
    "standard_lander",
    "standard_dispatcher",
    "standard_bleacher",
    "standard_stainer",
    "standard_observer",
    "gate_passthrough",
    "standard_retry_logic",
    "standard_sleep",
    "standard_egress",
    "drain_signal",
    "halt_signal",
    "resource_requestor",
    "discrete_allocator",
    "discrete_reclaimer",
    "continuous_allocator",
    "continuous_reclaimer",
]
~~~~~

### 下一步建议

基础组件已经就绪。

下一步任务：
1.  **修改编译器 (`cascade-compiler`)**:
    *   更新 `Expander` 逻辑，从生成 `Bleach/Worker/Stain` 三联体转变为生成 `Launcher/Lander` 二元体。
    *   **关键**: 确保 Expander 在创建 `LauncherNode` 时，通过 `PhysicalIdGenerator` 获取 `Lander` 前置的数据节点 ID (`D_result`)，并将其赋值给 `reply_to_nid` 字段。
2.  **更新 Linker (`cascade-vm`)**:
    *   注册新的 `Launcher` 和 `Lander` IC 到 Kernel Function Map。
