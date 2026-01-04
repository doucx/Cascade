简要回答
我们正在实施 Phase 4，核心是将 `run_id` 的生成与注入职责从“资源注册表”转移到“物理场创世时刻”。这将通过 `Token.trace` 实现全链路的上下文传播。

## [WIP] feat(vm): 实施基于 Trace 的上下文注入协议 (Phase 4)

### 用户需求
实施“创世注入 (Genesis Injection)”模式：
1.  **Run ID 生成**: `EventDrivenRunner` 在实例化时生成唯一的 `run_id`。
2.  **创世注入**: 通过 `Reactor.prime()` 和 `Runner.inject_input()`，将 `run_id` 作为初始动量注入到首批 Token 的 `trace` 中。
3.  **迹流传播**: `Bleacher` 和 `Stainer` 从 Token Trace 中提取 `run_id` 并填入 `EventIR` 的 `ctx` 字段，从而实现无状态物理节点的上下文感知。

### 评论
这是一个架构上的关键转折点。它移除了物理层对全局 `ResourceRegistry` 获取上下文的隐式依赖，转而使用符合物理学隐喻的“粒子携带历史”模型。这不仅解决了 `run_id` 的传递问题，也为未来支持分布式追踪（OpenTelemetry）打下了坚实的理论基础。

### 目标
1.  更新 `ReactorProtocol` 和 `Reactor` 的 `prime` 接口以支持 `genesis_trace`。
2.  升级 `EventDrivenRunner` 以管理 `run_id` 并执行注入。
3.  更新标准库中的 `bleacher` 和 `stainer` 以在生成遥测事件时使用 Trace 中的上下文。

### 基本原理
根据《Cascade 3.0 架构白皮书》及“创世注入”补遗，物理节点应保持无状态（局域性原理）。上下文信息（如 Run ID）应作为 Token 的属性（Trace）在网络中流动，而不是存储在全局变量或注入的资源中。这保证了并行执行的隔离性和系统的可观测性。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/runtime #comp/library #concept/observability #task/domain/observability #task/object/context-injection #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 VM 协议与反应堆接口

我们首先修改 `ReactorProtocol` 和 `Reactor` 的 `prime` 方法，允许在系统启动时注入初始 Trace 数据（即“创世微扰”）。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python.old
class ReactorProtocol(Protocol):
    active_task_count: int

    def prime(self) -> None: ...

    async def step(self) -> int: ...
~~~~~
~~~~~python.new
from typing import Protocol, Callable, Awaitable, Dict, Any, Optional
from cascade.spec.physics import Token


class ReactorProtocol(Protocol):
    active_task_count: int

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    async def step(self) -> int: ...
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def prime(self) -> None:
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    self.memory.put(node, Token(payload=node.initial_payload))

    async def step(self) -> int:
~~~~~
~~~~~python.new
    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    # We inject the genesis trace (e.g. run_id) into these primordial tokens.
                    self.memory.put(
                        node,
                        Token(
                            payload=node.initial_payload, trace=genesis_trace.copy()
                        ),
                    )

    async def step(self) -> int:
~~~~~

#### Acts 2: 升级 EventDrivenRunner (创世者)

`EventDrivenRunner` 作为物理场的上帝（Harness），负责定义“我是谁”（Run ID）。我们将修改它以生成 UUID，并在 `prime()` 和 `inject_input()` 时将其注入系统。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
import asyncio
import logging
from typing import Dict, Any, Callable, TypeVar, Optional, List

from cascade.spec.topology import BipartiteGraph
~~~~~
~~~~~python.new
import asyncio
import logging
import uuid
from typing import Dict, Any, Callable, TypeVar, Optional, List

from cascade.spec.topology import BipartiteGraph
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        # Register the bus so standard_observer can find it
        self.resource_registry.register("system.event_bus", self.event_bus)

        # Bridge Bus -> Queue for testing
        self.event_bus.subscribe(Event, self._on_event)

        # 2. The function map is now used directly
~~~~~
~~~~~python.new
        # Register the bus so standard_observer can find it
        self.resource_registry.register("system.event_bus", self.event_bus)

        # 1.1 Genesis Identity
        self.run_id = str(uuid.uuid4())

        # Bridge Bus -> Queue for testing
        self.event_bus.subscribe(Event, self._on_event)

        # 2. The function map is now used directly
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    def _on_event(self, event: Event):
        self.event_queue.put_nowait(event)

    def prime(self):
        self.reactor.prime()

    async def start_loop(self):
~~~~~
~~~~~python.new
    def _on_event(self, event: Event):
        self.event_queue.put_nowait(event)

    def prime(self):
        # Genesis Injection: Inject the run_id into the initial static tokens
        self.reactor.prime(genesis_trace={"rid": self.run_id})

    async def start_loop(self):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
            self._loop_task = None

    def inject_input(self, node_id: str, payload: Any):
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        self.memory.put(node, Token(payload=payload))

    async def wait_for_event(
        self,
~~~~~
~~~~~python.new
            self._loop_task = None

    def inject_input(
        self, node_id: str, payload: Any, trace: Optional[Dict[str, Any]] = None
    ):
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")

        # Merge user trace with genesis trace (run_id)
        final_trace = {"rid": self.run_id}
        if trace:
            final_trace.update(trace)

        self.memory.put(node, Token(payload=payload, trace=final_trace))

    async def wait_for_event(
        self,
~~~~~

#### Acts 3: 适配标准库 (Bleacher & Stainer)

最后，我们更新 `standard_bleacher` 和 `standard_stainer`。它们现在需要从 Token 的 Trace 中读取 `rid`，并将其填入 `EventIR` 的 `ctx` 字段中，从而完成全息投影。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        state = EventState.FAILED
        error_msg = str(result_payload)

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
~~~~~

### 下一步建议

现在 `run_id` 已经在系统中流动。下一步，我们需要验证这个机制是否工作正常。建议创建一个集成测试，使用 `EventDrivenRunner` 运行一个简单的图，并断言生成的 `EventIR` 中确实包含了正确的 `ctx.rid`。这标志着 Phase 4 的完成。
