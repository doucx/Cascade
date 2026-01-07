import pytest
from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker, LinkerError

# Standard library function imports for manual wiring (simulating current behavior)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


@task
def missing_task():
    return "I do not exist"


@pytest.mark.asyncio
async def test_blind_optimism_without_linker():
    """
    Demonstrates that without the Linker, the VM starts even if code is missing,
    leading to a runtime failure (or "blind optimism").
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry (INTENTIONALLY MISSING CODE)
    code_registry = CodeRegistry()
    # We do NOT register missing_task here.

    # 3. Manual Wiring (The "Old Way")
    # This bypasses any integrity checks.
    func_map = {}
    for node_id in assembly.graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = standard_dispatcher
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize Runner
    # This should succeed currently, which is the problem.
    runner = EventDrivenRunner(assembly.graph, func_map, code_registry)
    runner.prime()

    # 5. Run
    # It will fail at runtime when Dispatcher tries to find the code hash,
    # or when ComputeService tries to load it.
    await runner.start_loop()
    try:
        # We expect it to timeout or fail, but NOT raise LinkerError at startup.
        # For this test, we just assert that we reached this point without error.
        assert True
    finally:
        await runner.stop_loop()


@pytest.mark.asyncio
async def test_linker_enforces_integrity():
    """
    Demonstrates that the Linker correctly identifies missing code and prevents startup.
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Use Linker
    linker = Linker()

    # 4. Assert LinkerError
    with pytest.raises(LinkerError) as excinfo:
        linker.link(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_runner_from_assembly_enforces_linker():
    """
    Demonstrates that using EventDrivenRunner.from_assembly() creates a safe, validated runtime.
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Assert Initialization Failure
    # Attempting to create the runner should fail immediately
    with pytest.raises(LinkerError) as excinfo:
        EventDrivenRunner.from_assembly(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)