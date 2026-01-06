## [WIP] fix(tests): 适配同步 Reactor 并修复测试套件

### 用户需求

修复因废除 `PhysicsExecutor` 和将 `Reactor` 转为同步模式而导致的测试失败。需要清理所有旧的异步调用模式，并确保测试代码与新的内核架构保持一致。

### 评论

这次修复不仅是清理导入错误，更是对测试逻辑的根本性更新。由于 `Reactor` 现在是同步直驱的，之前用于等待异步任务完成的 `wait_idle` 循环现在是多余且错误的。移除它们将显著提高测试速度。同时，我们需要修正 `EventDrivenRunner` 中的逻辑错误，确保它正确调用同步的 `step()` 方法。

### 目标

1.  删除已废弃的 `packages/cascade-vm/tests/unit/test_executor.py`。
2.  修正 `packages/cascade-vm/src/cascade/vm/harness.py` 中对 `reactor.step()` 的调用（移除 `await`）。
3.  更新所有集成测试和单元测试：
    *   移除 `PhysicsExecutor` 的导入和实例化。
    *   更新 `Reactor` 的构造函数调用。
    *   移除 `await reactor.step()` 中的 `await`。
    *   移除所有 `wait_idle` 循环。

### 基本原理

新的物理内核遵循“直驱”原则，`reactor.step()` 返回时，所有激发的计算步骤均已完成。因此，测试代码必须反映这一现实，去除人为的异步等待，直接断言状态。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/vm #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/repair #task/state/continue

---

### Script

#### Acts 1: 删除废弃的测试文件

~~~~~act
delete_file
packages/cascade-vm/tests/unit/test_executor.py
~~~~~

#### Acts 2: 修复 Harness 中的逻辑错误

修正 `EventDrivenRunner` 调用同步 `step` 的方式。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    async def _run_loop(self):
        logger.info("Reactor loop with ingress handling started.")
        try:
            while not self._stop_event.is_set():
                # In v3.1 Phase 4, the Reactor handles ingress internally during step().
                fired = await self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
~~~~~
~~~~~python.new
    async def _run_loop(self):
        logger.info("Reactor loop with ingress handling started.")
        try:
            while not self._stop_event.is_set():
                # In v3.1 Phase 4, the Reactor handles ingress internally during step().
                fired = self.reactor.step()
                if fired == 0 and self.ingress_queue.empty():
                    await asyncio.sleep(0.001)
                else:
                    # Yield to allow other tasks (like ComputeService) to run
                    await asyncio.sleep(0)
~~~~~

#### Acts 3: 修复 test_reactor.py

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
~~~~~
~~~~~python.new
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.harness import EventDrivenRunner
from cascade.spec.physical.triad import ObservabilityNode
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_reactor_step_idle(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    fired_count = await reactor.step()

    assert fired_count == 0


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
async def test_reactor_step_idle(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, function_map)

    fired_count = reactor.step()

    assert fired_count == 0


@pytest.mark.asyncio
async def test_reactor_step_fire(simple_topology):
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, function_map)

    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1

    # 2. Step
    fired_count = reactor.step()

    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(d2.id, "out", f1.id, target_port="in2"))

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)

    # Only fill D1
    memory.put(d1, Token(payload="A"))

    fired_count = await reactor.step()

    assert fired_count == 0
    # Token in D1 should remain untouched
    assert memory.get_count(d1.id) == 1


@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
~~~~~
~~~~~python.new
    graph.channels.append(Channel(d2.id, "out", f1.id, target_port="in2"))

    memory = VolatileMemory()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, function_map)

    # Only fill D1
    memory.put(d1, Token(payload="A"))

    fired_count = reactor.step()

    assert fired_count == 0
    # Token in D1 should remain untouched
    assert memory.get_count(d1.id) == 1


@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
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
    graph.channels.append(Channel(d1.id, "out", f1.id, target_port="in"))
    graph.channels.append(Channel(d2.id, "out", f2.id, target_port="in"))

    memory = VolatileMemory()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, function_map)

    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))

    fired_count = reactor.step()

    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0
~~~~~

#### Acts 4: 修复 test_broker_starvation.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.std.resource.discrete import (
    discrete_allocator,
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.std.resource.discrete import (
    discrete_allocator,
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
async def wait_idle(reactor):
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)


def create_starvation_topology(allocator_first: bool):
    # Setup:
~~~~~
~~~~~python.new
def create_starvation_topology(allocator_first: bool):
    # Setup:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_allocator_starves_reclaimer():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=True
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)
    reactor.prime()

    # Step 1
    # Allocator should fire (it sees Ledger and Req).
    # Reclaimer sees Ledger and Rel, BUT Ledger is consumed by Allocator first.
    fired = await reactor.step()
    await wait_idle(reactor)

    assert fired == 1

    # Check Ledger State: Should still be 0 available (Allocator failed and returned it)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 0

    # Check D_rel: Should still be 1 (Reclaimer didn't run)
    assert memory.get_count(d_rel.id) == 1

    # Step 2
    # Allocator fires AGAIN.
    fired = await reactor.step()
    await wait_idle(reactor)

    assert fired == 1
    assert memory.get_count(d_rel.id) == 1  # Reclaimer STILL hasn't ran


@pytest.mark.asyncio
async def test_reclaimer_priority_fixes_starvation():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=False
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)
    reactor.prime()

    # Step 1
    # Reclaimer should fire first.
    fired = await reactor.step()
    await wait_idle(reactor)

    assert fired >= 1  # Could be 1 (Reclaim) or 2 (Reclaim then Alloc in same step?)
    # Wait, in one step, if Reclaim consumes Ledger, Allocator CANNOT fire in that same step.
    # So fired should be 1.

    # Check Ledger State: Should be 1 available (Reclaimed)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 1

    # Check D_rel: Should be 0 (Consumed)
    assert memory.get_count(d_rel.id) == 0

    # Step 2
    # Now Allocator should fire and SUCCEED
    fired = await reactor.step()
    await wait_idle(reactor)

    # Ledger should be 0 again (Granted)
    ledger = memory.take(d_ledger.id).payload
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_allocator_starves_reclaimer():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=True
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)
    reactor.prime()

    # Step 1
    # Allocator should fire (it sees Ledger and Req).
    # Reclaimer sees Ledger and Rel, BUT Ledger is consumed by Allocator first.
    fired = reactor.step()

    assert fired == 1

    # Check Ledger State: Should still be 0 available (Allocator failed and returned it)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 0

    # Check D_rel: Should still be 1 (Reclaimer didn't run)
    assert memory.get_count(d_rel.id) == 1

    # Step 2
    # Allocator fires AGAIN.
    fired = reactor.step()

    assert fired == 1
    assert memory.get_count(d_rel.id) == 1  # Reclaimer STILL hasn't ran


@pytest.mark.asyncio
async def test_reclaimer_priority_fixes_starvation():
    graph, d_ledger, d_req, d_rel, func_map = create_starvation_topology(
        allocator_first=False
    )

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)
    reactor.prime()

    # Step 1
    # Reclaimer should fire first.
    fired = reactor.step()

    assert fired >= 1  # Could be 1 (Reclaim) or 2 (Reclaim then Alloc in same step?)
    # Wait, in one step, if Reclaim consumes Ledger, Allocator CANNOT fire in that same step.
    # So fired should be 1.

    # Check Ledger State: Should be 1 available (Reclaimed)
    ledger = memory.take(d_ledger.id).payload
    memory.put(d_ledger, Token(payload=ledger))
    assert ledger.available == 1

    # Check D_rel: Should be 0 (Consumed)
    assert memory.get_count(d_rel.id) == 0

    # Step 2
    # Now Allocator should fire and SUCCEED
    fired = reactor.step()

    # Ledger should be 0 again (Granted)
    ledger = memory.take(d_ledger.id).payload
~~~~~

#### Acts 5: 修复 test_observability_congestion.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor


def noop_producer(inputs, node, resources):
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor


def noop_producer(inputs, node, resources):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        PhysicsExecutor(),
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
    # Both F_p1 and F_p2 are ready. They will try to fire in the same step.
    # D_life has capacity 1.
    # One will succeed, the other SHOULD fail with MemoryFullError.

    try:
        await reactor.step()
    except Exception as e:
        # We expect a crash here due to atomic consumption but separate emission
~~~~~
~~~~~python.new
    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
    # Both F_p1 and F_p2 are ready. They will try to fire in the same step.
    # D_life has capacity 1.
    # One will succeed, the other SHOULD fail with MemoryFullError.

    try:
        reactor.step()
    except Exception as e:
        # We expect a crash here due to atomic consumption but separate emission
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        PhysicsExecutor(),
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
    # Both should fire successfully.
    fired = await reactor.step()

    import asyncio

    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)

    assert fired == 2
    assert memory.get_count(d_life.id) == 2
~~~~~
~~~~~python.new
    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
    # Both should fire successfully.
    fired = reactor.step()

    assert fired == 2
    assert memory.get_count(d_life.id) == 2
~~~~~

#### Acts 6: 修复 test_ping_pong.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor


def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~
~~~~~python.new
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor


def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    executor = PhysicsExecutor()
    reactor = Reactor(graph, memory, executor, function_map)

    # 1. Start state
    initial_token = Token(payload=10)
    memory.put(d1, initial_token)

    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()

    # Wait for async completion
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)

    # 3. Assertions
    assert fired_count == 1
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, function_map)

    # 1. Start state
    initial_token = Token(payload=10)
    memory.put(d1, initial_token)

    # 2. Run the physics simulation for one step
    fired_count = reactor.step()

    # 3. Assertions
    assert fired_count == 1
~~~~~

#### Acts 7: 修复 test_resource_backpressure.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    func_map = {}
~~~~~
~~~~~python.new
    # 3. Setup VM
    memory = VolatileMemory()

    # Map functions
    func_map = {}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)

    reactor = Reactor(
        physical_graph, memory, executor, func_map, resource_registry=registry
    )

    # 6. Prime the reactor.
    reactor.prime()
~~~~~
~~~~~python.new
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)

    reactor = Reactor(
        physical_graph, memory, func_map, resource_registry=registry
    )

    # 6. Prime the reactor.
    reactor.prime()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # 7. Step Execution Logic
    async def wait_idle():
        import asyncio

        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

    # --- SIMULATION ---
    # The new graph has many more steps due to Probe -> Req -> Broker -> Bleacher

    # Round 1: Probes fire (providing Amount and X)
    await reactor.step()
    await wait_idle()

    # Round 2: Requestors fire (sending Req Tokens to Buffer)
    await reactor.step()
    await wait_idle()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer

    # Round 3: Allocator fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    await reactor.step()
    await wait_idle()

    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4:
    # - The lucky Bleacher (who got GNT) fires.
    # - The Allocator attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1).
    #   Logic: 0 < 1. Reject & Recirculate.

    await reactor.step()
    await wait_idle()

    # If Allocator fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.

    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer -> RelBuffer -> Reclaimer -> Ledger

    # We loop until resource is released (Ledger becomes 1)
    max_steps = 30
    for _ in range(max_steps):
        await reactor.step()
        await wait_idle()

        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break

    assert ledger.available == 1

    # Now the second task can proceed.
    # Allocator fires -> Grants -> Bleacher -> Worker -> Stainer -> Reclaimer
    for _ in range(20):
        if (
            memory.get_count(req_buffer_id) == 0
            and memory.get_count("buffer.rel.gpu") == 0
        ):
            # If buffers are empty and tasks done, we are good.
            pass
        await reactor.step()
        await wait_idle()

    # Final check: Ledger full, Buffers empty
~~~~~
~~~~~python.new
    # --- SIMULATION ---
    # The new graph has many more steps due to Probe -> Req -> Broker -> Bleacher

    # Round 1: Probes fire (providing Amount and X)
    reactor.step()

    # Round 2: Requestors fire (sending Req Tokens to Buffer)
    reactor.step()

    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer

    # Round 3: Allocator fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    reactor.step()

    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4:
    # - The lucky Bleacher (who got GNT) fires.
    # - The Allocator attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1).
    #   Logic: 0 < 1. Reject & Recirculate.

    reactor.step()

    # If Allocator fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.

    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer -> RelBuffer -> Reclaimer -> Ledger

    # We loop until resource is released (Ledger becomes 1)
    max_steps = 30
    for _ in range(max_steps):
        reactor.step()

        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break

    assert ledger.available == 1

    # Now the second task can proceed.
    # Allocator fires -> Grants -> Bleacher -> Worker -> Stainer -> Reclaimer
    for _ in range(20):
        if (
            memory.get_count(req_buffer_id) == 0
            and memory.get_count("buffer.rel.gpu") == 0
        ):
            # If buffers are empty and tasks done, we are good.
            pass
        reactor.step()

    # Final check: Ledger full, Buffers empty
~~~~~

#### Acts 8: 修复 test_branching.py

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor


def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor


def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
async def wait_for_idle(reactor: Reactor):
    while reactor.active_task_count > 0:
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))

    # 2. Run
    await reactor.step()
    await wait_for_idle(reactor)

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"

    # D_B should be empty (physically blocked)
    assert memory.get_count(d_b.id) == 0


@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, PhysicsExecutor(), func_map)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))

    # 2. Run
    await reactor.step()
    await wait_for_idle(reactor)

    # 3. Assert
    # D_B should receive token
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))

    # 2. Run
    reactor.step()

    # 3. Assert
    # D_A should receive token
    assert memory.get_count(d_a.id) == 1
    assert memory.take(d_a.id).payload == "Data A"

    # D_B should be empty (physically blocked)
    assert memory.get_count(d_b.id) == 0


@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))

    # 2. Run
    reactor.step()

    # 3. Assert
    # D_B should receive token
~~~~~

### 下一步建议

所有测试文件都已更新，去除了 `PhysicsExecutor` 并适配了同步的 `Reactor`。现在系统已经恢复到了一个一致的状态。

接下来，我们将继续执行 **“阶段 2: 桥接司法管辖区”**。我们将专注于验证：
1.  **`standard_dispatcher`** 是否正确地（同步地）将请求放入队列。
2.  **`standard_observer`** 是否正确地（同步地）将事件发布到总线。
3.  通过编写一个新的集成测试 `tests/vm/test_machine_integration.py`，验证 `Machine` 如何协调同步的内核与异步的计算服务。
