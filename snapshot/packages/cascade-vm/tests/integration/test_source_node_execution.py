import asyncio
import pytest
from typing import Dict

from cascade.spec.dsl.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


@task
def source_task():
    return "Pulse Fired!"


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

    # 2. Setup Code Registry for the Compute Service
    code_registry = CodeRegistry()
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)

    # 3. Build the function map for the Reactor
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            # All user workers are now handled by the dispatcher
            func_map[node_id] = standard_dispatcher
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Setup and run the VM using the new Harness
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    # 5. Execute
    await runner.start_loop()
    try:
        # 6. Assert the result by waiting for the completion event.
        # This now validates the full dispatch -> compute -> ingress loop.
        completion_event = await runner.run_until_complete(
            task_id=node_ir.current_node_instance_hash, timeout=5.0
        )

        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == node_ir.current_node_instance_hash

        # The result preview is now a Ref. To verify the content, we need to
        # access the runner's object store.
        result_ref = completion_event.result_preview
        final_result = runner.object_store.get(result_ref)
        assert final_result == "Pulse Fired!"

    finally:
        await runner.stop_loop()