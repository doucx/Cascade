import pytest

from cascade.spec.dsl.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.bus.events import TaskExecutionFinished
from cascade.spec.runtime.observability import EventState


@task
def source_task():
    return "Pulse Fired!"


@pytest.mark.asyncio
async def test_source_node_is_triggered_by_pulse():
    # 1. Compile the graph
    ir_generator = IRGenerator()
    builder = Builder()

    flow = source_task()
    generation_result = ir_generator.generate(flow)
    graph_ir = generation_result.ir
    node_ir = graph_ir.nodes[0]
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Code Registry for the Compute Service
    code_registry = CodeRegistry()
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)

    # 3. Setup and run the VM using the new Harness
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    # 4. Execute
    await runner.start_loop()
    try:
        # 6. Assert the result by waiting for the completion event.
        # This now validates the full dispatch -> compute -> ingress loop.
        completion_event = await runner.run_until_complete(
            task_id=node_ir.current_node_instance_hash, timeout=5.0
        )

        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status is EventState.SUCCEEDED
        assert completion_event.task_id == node_ir.current_node_instance_hash

        # The result preview is now a Ref. To verify the content, we need to
        # access the runner's object store.
        result_ref = completion_event.result_preview
        final_result = runner.object_store.get(result_ref)
        assert final_result == "Pulse Fired!"

    finally:
        await runner.stop_loop()
