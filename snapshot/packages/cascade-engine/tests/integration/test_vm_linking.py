import pytest
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
import cascade as cs


@pytest.mark.asyncio
async def test_vm_strategy_delegates_linking_to_vm_and_executes():
    """
    End-to-end integration test for the new purified architecture:
    1. Frontend compiles workflow -> CompilationResult(ir, symbol_table).
    2. Backend compiles ir -> Blueprint (with structure_hash, func is gone).
    3. VMExecutionStrategy passes Blueprint + symbol_table to the VM.
    4. VM executes, looking up functions via structure_hash in real-time.
    """

    @cs.task
    def echo(x):
        return x

    workflow = echo("hello_world")

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),  # Still needed for GraphStrategy, though not used by VMStrategy
        bus=MessageBus(),
    )

    # Run with VM enabled.
    # If linking fails inside the VM, it will raise a RuntimeError.
    # If the `func` field was expected anywhere, it would raise an AttributeError or TypeError.
    result = await engine.run(workflow, use_vm=True)

    assert result == "hello_world"
