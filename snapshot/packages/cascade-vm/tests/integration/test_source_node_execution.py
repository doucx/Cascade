import asyncio
import pytest
from typing import Dict

from cascade.spec.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.spec.physics import Token
from cascade.vm.harness import EventDrivenRunner
from cascade.runtime.events import TaskExecutionFinished


# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer


@task
def source_task():
    return "Pulse Fired!"


# This worker now places its result into the trace, so the final 'end'
# event can be inspected for correctness.
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    trace_from_bleacher = worker_input_token.trace

    result = "Unexpected worker call"
    # Use the stable semantic name for routing, not the volatile hash-based id
    if "source_task" in node.name:
        result = source_task.func()

    # The Stainer will see the result as a payload, not in the trace.
    # The trace is passed through for duration calculation etc.
    return {"worker_result": Token(payload=result, trace=trace_from_bleacher)}


async def wait_for_idle(runner: EventDrivenRunner, timeout: float = 1.0):
    start_time = asyncio.get_event_loop().time()
    while runner.reactor.active_task_count > 0:
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise asyncio.TimeoutError("Reactor did not become idle in time")
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_source_node_is_triggered_by_pulse():
    # 1. Compile the graph
    ir_generator = IRGenerator()
    builder = Builder()

    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 2. Build the function map
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 3. Setup and run the VM
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()

    # 4. Execute
    await runner.start_loop()
    try:
        # 5. Assert the result by waiting for the completion event
        # This is the robust way to test completion, not by checking transient memory.
        completion_event = await runner.run_until_complete(
            task_id=node_ir.current_node_instance_hash
        )

        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == node_ir.current_node_instance_hash
        assert completion_event.result_preview == "Pulse Fired!"

    finally:
        await runner.stop_loop()
