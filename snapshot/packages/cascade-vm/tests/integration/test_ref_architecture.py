import pytest

from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.probe.const import const_probe


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
    graph_ir = ir_generator.generate(workflow)
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 3. Register user code in the CodeRegistry
    # The key is the canonical hash, found in the symbol table
    code_registry = CodeRegistry()
    for node_id, canonical_hash in assembly.symbol_table.items():
        if "add_one" in node_id:
            code_registry.register(canonical_hash, add_one.func)
        elif "square" in node_id:
            code_registry.register(canonical_hash, square.func)

    # 4. Build the function map for the Reactor (Standard Library ICs)
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif "observer" in node_id:
            func_map[node_id] = standard_observer
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        # All user workers are now implemented by the dispatcher
        elif node_id in assembly.symbol_table:
            func_map[node_id] = standard_dispatcher

    # 5. Setup and prime the VM Harness
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    # 6. Start the reactor and compute service loops
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
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == final_task_id

        # The most important check: verify the final computed value.
        # This proves the entire round-trip (outbound dispatch -> compute -> inbound ingress) worked.
        result_ref = completion_event.result_preview
        final_result = runner.object_store.get(result_ref)
        assert final_result == (10 + 1) ** 2  # 121

    finally:
        await runner.stop_loop()