import pytest
from cascade.compiler.backend import Builder
from cascade.compiler.frontend import IRGenerator
from cascade.spec.dsl.task import task
from cascade.spec.physical.constants import NodePrefix
from cascade.spec.physical.environment import EnvironmentDef
from cascade.std.dyad.lander import standard_lander

# Standard library function imports
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.system.observer import standard_observer
from cascade.test_utils import EventDrivenRunner
from cascade.vm.linker import Linker, LinkerError
from cascade.vm.registry import CodeRegistry


@task
def missing_task():
    return "I do not exist"


@pytest.mark.asyncio
async def test_blind_optimism_without_linker():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Manual Wiring (Simulating current Linker logic)
    func_map = {}
    for node_id in assembly.graph.nodes:
        if node_id.endswith(f".{NodePrefix.LAUNCH}"):
            func_map[node_id] = standard_launcher
        elif node_id.endswith(f".{NodePrefix.LAND}"):
            func_map[node_id] = standard_lander
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize Runner
    runner = EventDrivenRunner(assembly.graph, func_map, code_registry)
    runner.prime()

    # 5. Run
    await runner.start_loop()
    try:
        assert True
    finally:
        await runner.stop_loop()


@pytest.mark.asyncio
async def test_linker_enforces_integrity():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Use Linker
    linker = Linker()

    # 4. Assert LinkerError
    with pytest.raises(LinkerError) as excinfo:
        linker.link(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)
