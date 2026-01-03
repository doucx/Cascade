import asyncio
import pytest
from typing import Dict

from cascade.spec.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.spec.physics import Token
from cascade.vm.harness import EventDrivenRunner, ObservedEvent


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

    # The Stainer will merge this into the final trace
    trace_from_bleacher["worker_result"] = result
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
    physical_graph = builder.build(graph_ir, EnvironmentDef())

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
        completion_event = await runner.run_until_complete(task_id=node_ir.id)

        assert isinstance(completion_event, ObservedEvent)
        assert completion_event.event_type == "end"

        # The stainer should have received the worker's result via the trace
        # and included it in the final trace data emitted to the observer.
        # Let's modify the mock worker to facilitate this.
        # NOTE: The Stainer merges the trace from the worker's output token.
        # So we need to ensure the worker puts its result there.
        final_trace = completion_event.trace_data

        # We need a way for the worker's result to end up in the final trace.
        # The Stainer receives the worker's result as a payload. It's not in the trace.
        # Let's adjust the test to be more realistic. The Stainer's output *payload*
        # is what matters for downstream tasks. The *event* just confirms completion.

        # The most important assertion is that the task completed successfully.
        # The fact that run_until_complete returned without a timeout is the primary success signal.
        # We can also check the trace for the node ID.
        assert final_trace.get("id") == node_ir.id
        assert "duration" in final_trace
        assert final_trace.get("worker_result") == "Pulse Fired!"

    finally:
        await runner.stop_loop()