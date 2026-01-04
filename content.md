简要回答
好的，我们将执行 Phase 3，改造物理层标准库组件 (`Bleacher`, `Stainer`, `Observer`) 以发射和处理 `EventIR`，并更新 `EventDrivenRunner` 以适配新的事件流架构。

## [WIP] feat(std): 改造物理发射源以支持 EventIR

### 用户需求
根据 [Cascade 3.0 实施路线图 (Phase 3)](docs/实施路线图：Cascade%203.0%20全息投影协议%20(Event%20IR).md)，需要将标准库中的物理节点改造为 `EventIR` 的发射源。
具体包括：
1.  **Bleacher**: 构造并输出 `LIFECYCLE` (RUNNING) 类型的 `EventIR`。
2.  **Stainer**: 构造并输出 `LIFECYCLE` (SUCCEEDED/FAILED) 类型的 `EventIR`。
3.  **Observer**: 改造为哑节点，从资源中获取总线并发布 IR。
4.  **Harness**: 更新 `EventDrivenRunner`，使其建立 `Bus -> Queue` 的桥接，以维持测试的可观测性。

### 评论
这是“全息投影”协议的物理实现阶段。通过这次改造，物理层将不再产生非标准的 trace 数据，而是产生符合协议的 IR。同时，`EventDrivenRunner` 的更新标志着我们的测试架构正式转向基于总线的事件验证模式，实现了“吃自己的狗粮”。

### 目标
1.  修改 `cascade.std.triad.bleacher`，使其在 `obs_output` 端口输出 `EventIR`。
2.  修改 `cascade.std.triad.stainer`，使其在 `obs_output` 端口输出 `EventIR`。
3.  修改 `cascade.std.triad.observer`，移除旧的 `ObservedEvent` 逻辑，改为调用 `system.event_bus.publish_ir`。
4.  修改 `cascade.vm.harness`，注入 `EventBus`，并实现从 Bus 到 `event_queue` 的转发，确保现有测试（经过少量适配后）能继续通过。

### 基本原理
-   **结构化发射**: Bleacher 和 Stainer 使用 `cascade.spec.observability` 中定义的 `EventIR`, `EventType`, `EventState` 构造数据。
-   **物理锚点**: 使用 `phy: {"nid": node.id}` 明确事件的物理来源。
-   **依赖反转**: Observer 不再依赖具体的 Queue 实现，而是依赖抽象的 Bus 协议（鸭子类型 `publish_ir`）。

### 标签
#intent/refine #intent/build #flow/ready #priority/high #comp/std #comp/vm #concept/observability #scope/core #ai/instruct #task/domain/observability #task/object/physical-emitter #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 改造 Bleacher 发射源

修改 `standard_bleacher` 以构建 `EventIR`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
from typing import Dict, Any, List
import time

from cascade.spec.physics import Token
from cascade.spec.triad import BleachNode
from cascade.spec.ports import PortRole


async def standard_bleacher(
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
            # We record the port name as a held resource.
            held_resources.append(port_name)
            # CRITICAL: Record the granted amount (payload) to trace.
            # This allows the Stainer to know how much to release later.
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload
        # Observability and Signals are processed for trace but not passed to worker

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    trace_payload["start_ts"] = time.monotonic()
    trace_payload["id"] = node.id.replace(".bleach", "")  # Add the logical node ID
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Create the output tokens
    # Pass the trace through to the worker so it can add to it
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    obs_token = Token(payload=None, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }
~~~~~
~~~~~python.new
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physics import Token
from cascade.spec.triad import BleachNode
from cascade.spec.ports import PortRole


async def standard_bleacher(
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
    start_ts = time.time() # Use wall clock for IR
    mono_ts = time.monotonic() # Use monotonic for internal duration calc
    
    logical_id = node.id.replace(".bleach", "")
    
    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    # Note: 'ctx' will be populated in Phase 4.
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": {}, 
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            # We don't have task_name easily here yet, will address in Phase 4
        }
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

#### Acts 2: 改造 Stainer 发射源

修改 `standard_stainer` 以构建 `EventIR`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
from typing import Dict
import time

from cascade.spec.physics import Token
from cascade.spec.triad import StainNode
from cascade.spec.ports import PortRole


from typing import Any


async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_ts = time.monotonic()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload

    # The trace from the worker token might have been augmented by the worker.
    # The trace_input_token is the one from the "wormhole" D_trace.
    # The most up-to-date trace is the one that came through the worker.
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration and update trace
    start_ts = trace_payload.get("start_ts", end_ts)  # Default to end_ts for duration=0
    duration = end_ts - start_ts
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_ts

    # 3. Create output tokens
    outputs = {}

    # 3.1 The main result
    # Sovereign Routing: We explicitly choose the 'output_default' port for success.
    # In the future, if result_payload is an Exception or Jump, we would route to
    # 'output_error' or other dynamic ports.
    outputs["output_default"] = Token(payload=result_payload, trace=trace_payload)

    # 4.2 Observability Event
    outputs["obs_output"] = Token(payload=None, trace=trace_payload)

    # 4.3 Resource Return (The Loop)
    # We iterate over the node's output ports to find all RESOURCE ports.
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Look up the amount to release from trace data
            # The Bleacher stored it under 'resource_amounts' -> 'res_{name}'
            # But the Stainer's output port might be named differently (e.g. 'rel_{name}' or just 'res_{name}')
            # Convention: If Stainer output is 'res_gpu', Bleacher input was 'res_gpu'.
            amount = 1  # Default fallback

            # Try to find the specific amount
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]

            # Emit token with the correct amount to replenish the broker
            outputs[port_name] = Token(payload=amount)

    return outputs
~~~~~
~~~~~python.new
from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physics import Token
from cascade.spec.triad import StainNode
from cascade.spec.ports import PortRole


async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_mono = time.monotonic()
    now_wall = time.time()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload

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
    
    # Determine Status (Simplified for now, assuming success if reached here)
    # Error handling logic will be refined in future phases
    state = EventState.SUCCEEDED
    error_msg = None
    
    # TODO: Check if result_payload is an Exception wrapper
    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": {},
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100] if state == EventState.SUCCEEDED else None
        }
    }

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result
    outputs["output_default"] = Token(payload=result_payload, trace=trace_payload)

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

#### Acts 3: 改造 Observer 为哑节点

修改 `standard_observer`，使其成为连接物理图与消息总线的通用网关。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Literal
from dataclasses import dataclass, field

from cascade.spec.physics import Token, PhysicsNode


@dataclass
class ObservedEvent:
    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Get queue from the resource registry
    # In a real run, this would be a proper ResourceRegistry instance.
    # In tests, it might be a mock or a simple dict-like object.
    queue = resources.get("system.observer.queue")

    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)

    # Observers do not return tokens into the graph
    return {}
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec import EventIR
from cascade.spec.physics import Token, PhysicsNode


async def standard_observer(
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
        # We assume the bus supports the 'publish_ir' protocol
        bus.publish_ir(ir)

    # Observers do not return tokens into the graph
    return {}
~~~~~

#### Acts 4: 升级 EventDrivenRunner

更新测试 Harness 以支持新的事件流架构，确保测试可继续运行。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.observer import ObservedEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()

        # 1. Setup Resource Registry and Observability Queue
        self.event_queue: asyncio.Queue[ObservedEvent] = asyncio.Queue()
        self._captured_events: List[ObservedEvent] = []
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.observer.queue", self.event_queue)

        # 2. The function map is now used directly
        self.function_map = function_map

        # 3. Inject the registry into the Reactor
        # Use provided factory or default to the Python Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            self.function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def prime(self):
        self.reactor.prime()
~~~~~
~~~~~python.new
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.event_bus import EventBus
from cascade.runtime.events import Event, TaskExecutionFinished

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()

        # 1. Setup Event Bus & Resource Registry
        self.event_bus = EventBus()
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._captured_events: List[Event] = []
        
        self.resource_registry = ResourceRegistry()
        # Register the bus so standard_observer can find it
        self.resource_registry.register("system.event_bus", self.event_bus)
        
        # Bridge Bus -> Queue for testing
        self.event_bus.subscribe(Event, self._on_event)

        # 2. The function map is now used directly
        self.function_map = function_map

        # 3. Inject the registry into the Reactor
        # Use provided factory or default to the Python Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            self.function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    def _on_event(self, event: Event):
        self.event_queue.put_nowait(event)

    def prime(self):
        self.reactor.prime()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    async def wait_for_event(
        self,
        predicate: Callable[[ObservedEvent], bool],
        timeout: float = 1.0,
    ) -> ObservedEvent:
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check timeout
            now = asyncio.get_event_loop().time()
            if now - start_time > timeout:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

            # Wait for next event
            try:
                # Calculate remaining time
                remaining = timeout - (now - start_time)
                event = await asyncio.wait_for(
                    self.event_queue.get(), timeout=remaining
                )
                self._captured_events.append(event)

                if predicate(event):
                    return event
            except asyncio.TimeoutError:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

    async def run_until_complete(
        self, task_id: str, timeout: float = 2.0
    ) -> ObservedEvent:
        def is_completion(e: ObservedEvent):
            # The Bleacher sets the 'id' in the trace.
            return e.event_type == "end" and e.trace_data.get("id") == task_id

        return await self.wait_for_event(is_completion, timeout=timeout)
~~~~~
~~~~~python.new
    async def wait_for_event(
        self,
        predicate: Callable[[Event], bool],
        timeout: float = 1.0,
    ) -> Event:
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check timeout
            now = asyncio.get_event_loop().time()
            if now - start_time > timeout:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

            # Wait for next event
            try:
                # Calculate remaining time
                remaining = timeout - (now - start_time)
                event = await asyncio.wait_for(
                    self.event_queue.get(), timeout=remaining
                )
                self._captured_events.append(event)

                if predicate(event):
                    return event
            except asyncio.TimeoutError:
                raise EventTimeoutError(f"Timed out waiting for event after {timeout}s")

    async def run_until_complete(
        self, task_id: str, timeout: float = 2.0
    ) -> Event:
        def is_completion(e: Event):
            # Updated to use the new TaskExecutionFinished event
            if isinstance(e, TaskExecutionFinished):
                # We match against the logical task_id which is now populated in the Event
                return e.task_id == task_id
            return False

        return await self.wait_for_event(is_completion, timeout=timeout)
~~~~~

### 下一步建议

完成 Phase 3 后，物理层已经能够产生标准化的 IR。但目前的 IR 中缺少关键的 `EventContext`（如 `run_id`）。
下一步我们将进行 **Phase 4: 上下文注入 (The Context Injection)**，在 `cascade-vm` 中实现环境资源的注入机制，确保 `Bleacher` 能够获取到运行时上下文并填入 `EventIR.ctx`。
