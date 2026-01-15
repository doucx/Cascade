import pytest

from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.bus.events import TaskExecutionFinished
from cascade.spec.runtime.observability import EventState


# --- User-defined tasks for the test ---
@task
def add_one(n: int) -> int:
    return n + 1


@task
def square(n: int) -> int:
    return n * n


@pytest.mark.asyncio
async def test_full_ref_based_e2e_flow():
    # 1. Define the logical workflow
    workflow = square(add_one(10))

    # 2. Compile into a physical Assembly
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    graph_ir = generation_result.ir
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 3. Register user code in the CodeRegistry
    # We need to map the physical ID back to the function.
    # We use the GraphIR to find the node ID for each task name.
    code_registry = CodeRegistry()

    # Helper to find canonical hash for a named task
    def register_task(task_name, func):
        # Find the NodeIR
        node_ir = next(n for n in graph_ir.nodes if n.name == task_name)
        # Construct the physical worker ID (Convention from PhysicalIdGenerator)
        worker_id = f"{node_ir.current_node_instance_hash}.worker"
        # Lookup canonical hash
        canonical_hash = assembly.symbol_table[worker_id]
        code_registry.register(canonical_hash, func)

    register_task("add_one", add_one.func)
    register_task("square", square.func)

    # 4. Setup and prime the VM Harness using the Linker-validated factory
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    # 5. Start the reactor and compute service loops
    await runner.start_loop()
    try:
        # 7. Wait for the final task in the chain to complete.
        # We identify the final node by its name from the IR.
        square_node_ir = next(n for n in graph_ir.nodes if n.name == "square")
        final_task_id = square_node_ir.current_node_instance_hash

        completion_event = await runner.run_until_complete(
            task_id=final_task_id, timeout=5.0
        )

        # 8. Assertions
        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status is EventState.SUCCEEDED
        assert completion_event.task_id == final_task_id

        # The most important check: verify the final computed value.
        # This proves the entire round-trip (outbound dispatch -> compute -> inbound ingress) worked.
        result_ref = completion_event.result_preview
        final_result = runner.object_store.get(result_ref)
        assert final_result == (10 + 1) ** 2  # 121

    finally:
        await runner.stop_loop()
