import asyncio
import pytest
from typing import Dict

from cascade.spec.task import task
from cascade.spec.ir.models import GraphIR
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.spec.physics import Token
from cascade.vm.harness import EventDrivenRunner

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.probe.const import const_probe
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor


@task
def source_task():
    """A simple task with no inputs."""
    return "Pulse Fired!"


# This is a generic worker that can be used if we need one
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    if node.id.startswith("source_task"):
        result = source_task.func()
        return {"worker_result": Token(payload=result)}
    return {"worker_result": Token(payload="Unexpected worker call")}


async def wait_for_idle(runner: EventDrivenRunner, timeout: float = 1.0):
    """Waits until the reactor has no more active tasks."""
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
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            # Map our specific worker
            if "source_task" in node_id:
                func_map[node_id] = mock_worker
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        # Add other stdlib funcs as needed for more complex graphs, not needed here

    # 3. Setup and run the VM
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()  # This should place the initial pulse token in memory

    # Verify priming
    pulse_node_id = f"pulse.source.{node_ir.id}"
    assert runner.memory.get_count(pulse_node_id) == 1

    # 4. Execute
    await runner.start_loop()
    try:
        await wait_for_idle(runner)

        # 5. Assert the result
        # The result of the worker is placed in the triad's output data node
        output_data_node_id = f"{node_ir.id}.data.out"
        assert runner.memory.get_count(output_data_node_id) == 1

        result_token = runner.memory.take(output_data_node_id)
        assert result_token.payload == "Pulse Fired!"
    finally:
        await runner.stop_loop()