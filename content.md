遵循 [Cascade 3.0 全系统集成迁移战略 (Phase 5)](../../01_current/当前任务/Cascade%203.0%20全系统集成迁移战略%20(Phase%205).md) 的指示，开始执行 **阶段 1：物理层的完备化**。

本计划将涵盖 Task 1.1 (Spec 扩展) 和 Task 1.2 (VM 升级)。我们将把 Reactor 从同步步进模型升级为**异步非阻塞模型**，并引入必要的内存事件通知机制。这是一个破坏性变更，因此我们将同步更新受影响的单元测试。

简要回答：
升级 `cascade-spec` 添加标准端口定义，重构 `cascade-vm` 实现异步 Reactor 和事件驱动内存，并更新相关测试。

## [WIP] refactor(vm): 升级 Reactor 为异步非阻塞模型并扩展物理定义

### 用户需求
1.  **标准化端口名称**: 在 `cascade-spec` 中定义 `PortName` 常量，避免硬编码字符串。
2.  **异步物理引擎**: 将 `Reactor` 改造为非阻塞模式。`step()` 仅负责调度任务，不等待执行完成。
3.  **状态可观测性**: 在 `Reactor` 中增加 `active_task_count` 计数器和 `add_sink` 接口，以便 Strategy 层监控系统状态和获取结果。
4.  **事件驱动内存**: `VolatileMemory` 需要在数据写入时触发 `asyncio.Event`，支持 `wait_for_mutation`。

### 评论
这是 Cascade 3.0 向“真实物理模拟”迈出的关键一步。通过将调度（Step）与执行（Execute）解耦，我们能够支持细粒度的并发和非阻塞 IO，同时 `active_task_count` 和 `sink` 机制为上层 Strategy 提供了必要的控制抓手。

### 目标
1.  在 `cascade-spec` 中添加 `PortName`。
2.  在 `cascade-vm` 中实现 `VolatileMemory.wait_for_mutation`。
3.  重写 `Reactor.step` 和 `Reactor._fire`，实现 fire-and-forget 调度。
4.  更新所有受影响的 Reactor 单元测试，确保它们能正确处理异步结果。

### 基本原理
目前的 `Reactor.step` 是阻塞的，这限制了并发能力且不符合 "Physics Field" 的连续演化特性。通过引入异步发射和 `active_task_count`，我们允许 Reactor 在任务执行期间继续扫描或休眠，直到状态发生变化（Mutation），这更符合 Actor 模型和事件驱动架构。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/runtime #concept/state #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/physics-layer #task/action/completion #task/state/begin #task/status/active

---

### Script

#### Acts 1: 扩展物理定义 (Spec)

在 `ports.py` 中增加标准端口名称定义，用于统一资源、Trace 和 Worker 的接口命名。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ports.py
~~~~~
~~~~~python.old
@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"
~~~~~
~~~~~python.new
@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"


class PortName:
    # Resources
    REQ = "req_in"
    REL = "rel_in"
    GNT = "gnt_out"
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"

    # Worker
    WORKER_INPUT = "worker_input"
    WORKER_RESULT = "worker_result"

    # Trace
    TRACE_INPUT = "trace_input"
    TRACE_OUTPUT = "trace_output"

    # Observability
    OBS_OUTPUT = "obs_output"
    EVENT_TOKEN = "event_token"
~~~~~

#### Acts 2: 升级内存模型 (VM)

改造 `VolatileMemory`，增加 `wait_for_mutation` 支持，使其成为事件驱动的存储。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/memory.py
~~~~~
~~~~~python.old
from typing import Dict
from collections import deque
from cascade.spec.physics import Token, PhysicsDataNode


class MemoryError(Exception):
~~~~~
~~~~~python.new
from typing import Dict
import asyncio
from collections import deque
from cascade.spec.physics import Token, PhysicsDataNode


class MemoryError(Exception):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/memory.py
~~~~~
~~~~~python.old
class VolatileMemory:
    def __init__(self):
        # Maps node_id -> deque of Tokens
        self._buffers: Dict[str, deque[Token]] = {}
        # Maps node_id -> capacity
        self._capacities: Dict[str, int] = {}

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        node_id = node.id
        if node_id not in self._buffers:
            self._buffers[node_id] = deque()
            self._capacities[node_id] = node.capacity

        buffer = self._buffers[node_id]
        capacity = self._capacities[node_id]

        if len(buffer) >= capacity:
            raise MemoryFullError(
                f"Node '{node.name}' ({node_id}) with capacity {capacity} is full."
            )

        buffer.append(token)

    def take(self, node_id: str) -> Token:
~~~~~
~~~~~python.new
class VolatileMemory:
    def __init__(self):
        # Maps node_id -> deque of Tokens
        self._buffers: Dict[str, deque[Token]] = {}
        # Maps node_id -> capacity
        self._capacities: Dict[str, int] = {}
        self._mutation_event = asyncio.Event()

    async def wait_for_mutation(self) -> None:
        """Wait until a new token is put into memory."""
        await self._mutation_event.wait()
        self._mutation_event.clear()

    def put(self, node: PhysicsDataNode, token: Token) -> None:
        node_id = node.id
        if node_id not in self._buffers:
            self._buffers[node_id] = deque()
            self._capacities[node_id] = node.capacity

        buffer = self._buffers[node_id]
        capacity = self._capacities[node_id]

        if len(buffer) >= capacity:
            raise MemoryFullError(
                f"Node '{node.name}' ({node_id}) with capacity {capacity} is full."
            )

        buffer.append(token)
        self._mutation_event.set()

    def take(self, node_id: str) -> Token:
~~~~~

#### Acts 3: 升级 Reactor 为异步非阻塞模型 (VM)

这将是一个较大的重构。我们需要：
1.  添加 `active_task_count` 和 `sinks`。
2.  将 `step` 改为只调度不等待。
3.  将执行逻辑移至后台任务 `_execute_task`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python
import asyncio
import inspect
import logging
from typing import List, Callable, Dict, Tuple, Awaitable
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map

        # State
        self.active_task_count = 0
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
        # node_id -> List[(source_data_node_id, target_port_name)]
        self._func_inputs: Dict[str, List[Tuple[str, str]]] = {}
        # node_id -> List[Channel]
        self._outbound_channels: Dict[str, List[Channel]] = {}

        # 1. Identify Function Nodes
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []
                self._outbound_channels[node.id] = []

        # 2. Build Connectivity Index
        for channel in self.graph.channels:
            source = self.graph.nodes.get(channel.source_node_id)
            target = self.graph.nodes.get(channel.target_node_id)

            if not source or not target:
                continue

            # Case A: Data -> Func (Input wiring)
            if isinstance(source, PhysicsDataNode) and isinstance(
                target, PhysicsFuncNode
            ):
                # Record that Target(F) needs input from Source(D) on specific Port
                self._func_inputs[target.id].append((source.id, channel.target_port))

            # Case B: Func -> Data (Output wiring)
            elif isinstance(source, PhysicsFuncNode) and isinstance(
                target, PhysicsDataNode
            ):
                # Record the full channel to support filtering logic later
                self._outbound_channels[source.id].append(channel)

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None:
        """Register a callback to receive tokens emitted by a specific port."""
        if node_id not in self.sinks:
            self.sinks[node_id] = {}
        if port_name not in self.sinks[node_id]:
            self.sinks[node_id][port_name] = []
        self.sinks[node_id][port_name].append(callback)

    def prime(self) -> None:
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    self.memory.put(node, Token(payload=node.initial_payload))

    async def step(self) -> int:
        """
        Scans the graph for excited nodes and schedules them for execution.
        Returns the number of tasks scheduled (fired) in this step.
        This method is NON-BLOCKING regarding task execution.
        """
        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
        # This loop is single-threaded and sequential. The state of `memory`
        # changes within the loop, ensuring that a resource token consumed by an
        # early node is unavailable for a later node in the same step.
        for f_node in self._func_nodes:
            inputs_def = self._func_inputs.get(f_node.id, [])
            if not inputs_def:
                continue

            # Check if this node CAN fire based on the CURRENT memory state
            if all(self.memory.is_excited(src_id) for src_id, _ in inputs_def):
                # It can. Atomically consume its inputs NOW.
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

        # Schedule execution
        for node in nodes_to_fire:
            self._schedule_task(node, inputs_for_fire[node.id])

        return len(nodes_to_fire)

    def _schedule_task(self, node: PhysicsFuncNode, input_data: Dict[str, Token]):
        self.active_task_count += 1
        asyncio.create_task(self._execute_task(node, input_data))

    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
            if not func:
                raise ValueError(f"No function mapped for node {node.id}")

            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node)
            else:
                result_tokens = await self.executor.submit(func, (input_data, node))

            if not isinstance(result_tokens, dict):
                raise ValueError(
                    f"Function for node {node.id} must return a Dict[str, Token], "
                    f"got {type(result_tokens)}"
                )

            # 2. Emission & Sinks
            outbound = self._outbound_channels.get(node.id, [])
            node_sinks = self.sinks.get(node.id, {})

            # We iterate over all result tokens to handle both Sinks and Channels
            for port_name, token in result_tokens.items():
                if token is None:
                    continue

                # A. Handle Sinks (Direct callback)
                if port_name in node_sinks:
                    for cb in node_sinks[port_name]:
                        try:
                            await cb(token)
                        except Exception as e:
                            logger.exception(f"Sink callback failed for {node.id}:{port_name}: {e}")

                # B. Handle Outbound Channels (Topological Flow)
                # Find channels connected to this source port
                matching_channels = [
                    c for c in outbound if c.source_port == port_name
                ]
                
                for channel in matching_channels:
                    # Spectrum Filtering
                    if channel.tag_filter and channel.tag_filter != token.tag:
                        continue

                    target_node = self.graph.nodes[channel.target_node_id]
                    if isinstance(target_node, PhysicsDataNode):
                        self.memory.put(target_node, token)

        except Exception as e:
            logger.exception(f"Error executing task {node.id}: {e}")
            # TODO: Emit error token to a special error port or DLQ?
            # For now, we just log. In v3.0 specs, errors are propagated as tokens.
            # If the func raised, it means it crashed HARD.
        finally:
            self.active_task_count -= 1
            # If we hit 0, we might want to signal an event?
            # For now, relying on memory mutation events is enough for forward progress.
~~~~~

#### Acts 4: 更新 Reactor 测试 (VM)

旧的 `test_reactor.py` 假设 `step()` 是同步的。我们需要引入等待机制。由于我们刚刚给 `VolatileMemory` 加了 `wait_for_mutation`，我们可以用它来同步测试。

但是，`Reactor` 测试使用的是 `VolatileMemory`。我们需要一个 helper 来等待结果出现。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_reactor_step_fire(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1

    # 2. Step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_reactor_step_fire(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1

    # 2. Step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0

    # 4. Wait for execution to finish (async reactor)
    # The output token should eventually appear in a downstream node if there was one.
    # In this topology (D1->F1), F1 has an output port 'out' but no downstream channel in simple_topology fixture?
    # Let's check the fixture.
    # Ah, simple_topology only has D1->F1. F1 outputs to 'out' but it goes nowhere.
    # So we can't check memory for result.
    # But we can check active_task_count.
    import asyncio

    # Wait until task finishes
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)

    # Success if we reached here without hanging
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = await reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0
~~~~~
~~~~~python.new
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = await reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0

    # Wait for completion
    import asyncio

    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)
~~~~~

#### Acts 5: 更新其他集成测试 (Integration)

`test_ping_pong.py` 和 `test_branching.py` 也需要等待结果。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
~~~~~
~~~~~python.new
    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # 3. Assertions
    assert fired_count == 1

    # Input token should be consumed
    assert memory.get_count(d1.id) == 0

    # Wait for result to appear in memory
    await memory.wait_for_mutation()

    # Output node should receive the result
    assert memory.get_count(d2.id) == 1

    result_token = memory.take(d2.id)
    assert result_token.payload == 11  # 10 + 1
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
    # 2. Run
    await reactor.step()

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"
~~~~~
~~~~~python.new
    # 2. Run
    await reactor.step()

    # Wait for async execution
    await memory.wait_for_mutation()

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
    # 2. Run
    await reactor.step()

    # 3. Assert
    # D_B should receive token
    assert memory.get_count(d_b.id) == 1
    assert memory.take(d_b.id).payload == "Data B"
~~~~~
~~~~~python.new
    # 2. Run
    await reactor.step()

    # Wait for async execution
    await memory.wait_for_mutation()

    # 3. Assert
    # D_B should receive token
    assert memory.get_count(d_b.id) == 1
    assert memory.take(d_b.id).payload == "Data B"
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await reactor.step()  # Stainer

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~
~~~~~python.new
    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await memory.wait_for_mutation() # Wait for Bleacher output
    await reactor.step() # Fire Worker

    # Step 3: Stainer fires.
    await memory.wait_for_mutation() # Wait for Worker output
    await reactor.step() # Fire Stainer

    # This should return the resource.
    await memory.wait_for_mutation() # Wait for Stainer output (release resource)

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await memory.wait_for_mutation() # Bleacher 2 done
    await reactor.step()  # Worker
    await memory.wait_for_mutation() # Worker 2 done
    await reactor.step()  # Stainer
    await memory.wait_for_mutation() # Stainer 2 done

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~

### 下一步建议
我们已经完成了物理层核心（Reactor & Memory）的异步改造，并更新了端口定义。下一步应该继续进行 **Task 1.3: 适配标准库 (`cascade-std`)**，确保所有的标准 IC（Bleacher, Stainer）都与新物理层兼容（虽然它们已经是 async 的，但我们需要再次确认其行为是否符合异步流），并开始实施 **阶段 2: 编译器的智能化**。
