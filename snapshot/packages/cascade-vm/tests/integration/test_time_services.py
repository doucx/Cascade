import asyncio
import time
import pytest
from typing import Dict, Callable

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.linker import Linker
from cascade.vm.registry import CodeRegistry

# Import the IC we are testing
from cascade.std.system.time import standard_sleep


async def wait_for_token(runner: EventDrivenRunner, node_id: str, timeout: float = 1.0):
    """Helper to wait until a token appears in a specific data node."""
    start_time = asyncio.get_event_loop().time()
    while runner.memory.get_count(node_id) == 0:
        await asyncio.sleep(0.01)
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise asyncio.TimeoutError(f"Token did not arrive at {node_id} within timeout")


@pytest.mark.asyncio
async def test_sleep_ic_delays_token():
    # 1. Setup Graph
    graph = BipartiteGraph()
    base_id = "task_with_delay"
    delay_duration = 0.1
    payload_data = {"message": "hello after delay"}

    # Node IDs
    d_delay_id = "d_delay_const"
    d_payload_id = "d_payload_const"
    f_sleep_id = PhysicalIdGenerator.sleep_node(base_id)
    d_wakeup_id = PhysicalIdGenerator.wakeup_data(base_id)

    # Node Definitions
    nodes = [
        PhysicsDataNode(id=d_delay_id, initial_tokens=1, initial_payload=delay_duration),
        PhysicsDataNode(id=d_payload_id, initial_tokens=1, initial_payload=payload_data),
        PhysicsFuncNode(
            id=f_sleep_id,
            name="Sleep",
            input_ports={
                "delay_in": PortDef("delay_in", PortRole.DATA),
                "data_in": PortDef("data_in", PortRole.DATA),
            },
        ),
        PhysicsDataNode(id=d_wakeup_id, name="Wakeup"),
    ]
    for node in nodes:
        graph.nodes[node.id] = node

    # Channels
    graph.channels.extend([
        Channel(d_delay_id, "out", f_sleep_id, "delay_in"),
        Channel(d_payload_id, "out", f_sleep_id, "data_in"),
        # There is no channel OUT of F_sleep. The result is injected back by Chronos.
    ])

    # 2. Setup Runner
    # The runner will wire up the ChronosService automatically.
    # The linker needs to know about our sleep function.
    function_map = {f_sleep_id: standard_sleep}
    code_registry = CodeRegistry()  # Not used, but required by runner

    runner = EventDrivenRunner(graph, function_map, code_registry)
    runner.prime()

    # 3. Execute and Measure
    await runner.start_loop()

    start_time = time.monotonic()
    
    # Wait for the token to arrive at the wakeup node
    await wait_for_token(runner, d_wakeup_id, timeout=delay_duration + 0.5)
    
    end_time = time.monotonic()

    # 4. Stop and Assert
    await runner.stop_loop()

    elapsed_time = end_time - start_time
    print(f"Requested Delay: {delay_duration}s, Actual Elapsed: {elapsed_time:.4f}s")

    # Assert time
    assert elapsed_time >= delay_duration
    # Assert correctness of data
    assert runner.memory.get_count(d_wakeup_id) == 1
    result_token = runner.memory.take(d_wakeup_id)
    assert result_token.payload == payload_data