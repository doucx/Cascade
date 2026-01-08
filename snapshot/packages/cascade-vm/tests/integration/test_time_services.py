import asyncio
import time
import pytest

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.runtime.storage import InMemoryObjectStore

# Standard Library ICs
from cascade.std.system.time import standard_sleep


@pytest.mark.asyncio
async def test_sleep_ic_integration():
    # 1. Setup Components
    memory = VolatileMemory()
    object_store = InMemoryObjectStore()

    # Queues
    compute_queue = asyncio.Queue()
    chronos_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    wakeup_event = asyncio.Event()

    # Registries
    code_registry = CodeRegistry()
    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.chronos_queue", chronos_queue)

    # 2. Build Physical Graph
    # Topology:
    #   D_delay (0.1s) --+
    #                    |--> F_sleep (vaporizes) ... (time passes) ... -> D_wakeup -> D_final
    #   D_data (payload) +

    base_id = "test_task"

    d_delay = PhysicsDataNode(id="d_delay", name="DelayInput")
    d_data = PhysicsDataNode(id="d_data", name="DataInput")

    # Using standard naming conventions via Generator
    f_sleep_id = PhysicalIdGenerator.sleep_node(base_id)
    d_wakeup_id = PhysicalIdGenerator.wakeup_data(base_id)

    f_sleep = PhysicsFuncNode(
        id=f_sleep_id,
        name="Sleep(0.1s)",
        input_ports={
            "delay_in": PortDef("delay_in", PortRole.DATA),
            "data_in": PortDef("data_in", PortRole.DATA),
        },
        # Output ports are empty because it returns nothing to the graph directly
    )

    # The wakeup node is a standard DataNode that receives the token back
    d_wakeup = PhysicsDataNode(id=d_wakeup_id, name="WakeupPoint")

    # We add a pass-through connection to a final node to verify flow continuation
    # For this simple test, we can just check D_wakeup, but let's be explicit

    graph = BipartiteGraph()
    graph.nodes[d_delay.id] = d_delay
    graph.nodes[d_data.id] = d_data
    graph.nodes[f_sleep.id] = f_sleep
    graph.nodes[d_wakeup.id] = d_wakeup

    # Wiring
    graph.channels.append(Channel(d_delay.id, "out", f_sleep.id, "delay_in"))
    graph.channels.append(Channel(d_data.id, "out", f_sleep.id, "data_in"))

    # Map the kernel function
    function_map = {f_sleep_id: standard_sleep}

    # 3. Instantiate Services & Machine
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)

    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )

    chronos_service = ChronosService(
        inbound_queue=chronos_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )

    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # 4. Inject Initial Tokens
    DELAY_SECONDS = 0.1
    TEST_PAYLOAD = "hello_future"

    memory.put(d_delay, Token(payload=DELAY_SECONDS))
    memory.put(d_data, Token(payload=TEST_PAYLOAD, trace={"origin": "past"}))

    # 5. Run & Measure
    start_time = time.monotonic()

    # Run the machine. We expect it to process the sleep request, pause,
    # have the ChronosService wait, re-inject, and then we manually stop it.
    # Since we don't have a self-terminating graph here (like DRAIN),
    # we'll run it as a background task and wait for the result in D_wakeup.

    machine_task = asyncio.create_task(machine.run())

    try:
        # We poll D_wakeup for the result
        while True:
            if memory.get_count(d_wakeup_id) > 0:
                break

            if time.monotonic() - start_time > 1.0:
                pytest.fail("Test timed out waiting for wakeup token")

            await asyncio.sleep(0.01)

        end_time = time.monotonic()
        duration = end_time - start_time

        # 6. Assertions
        print(f"Sleep Duration: {duration:.4f}s (Target: {DELAY_SECONDS}s)")

        # Verify Duration: Should be at least the delay, but not excessive overhead
        assert duration >= DELAY_SECONDS
        # Allow some buffer for async scheduling overhead, especially in CI
        assert duration < DELAY_SECONDS + 0.2

        # Verify Content
        result_token = memory.take(d_wakeup_id)
        assert result_token.payload == TEST_PAYLOAD
        assert result_token.trace["origin"] == "past"

    finally:
        # Cleanup
        reactor.shutdown_event.set()
        await machine_task
