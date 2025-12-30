import pytest
from unittest.mock import patch
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus

# NOTE: We expect this test to FAIL (AssertionError) initially.
# The current Engine implementation uses the old 'cascade.graph.compiler.BlueprintBuilder',
# so it will NOT call 'cascade.compiler.frontend.Frontend.compile'.

@pytest.mark.asyncio
async def test_engine_activates_new_compiler_pipeline():
    """
    Verifies that Engine.run(use_vm=True) delegates to the new cascade.compiler package
    instead of the legacy cascade.graph.compiler implementation.
    """
    # 1. Define a simple workflow
    @cs.task
    def add_one(x: int) -> int:
        return x + 1

    workflow = add_one(x=10)

    # 2. Setup Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 3. Patch the NEW Frontend to verify it gets called.
    # We patch it where it is defined.
    with patch("cascade.compiler.frontend.Frontend.compile") as mock_frontend_compile:
        # Mock the return value to avoid cascading errors downstream (if the wiring were partially complete)
        # But in the RED state, we expect the code to completely bypass this and use the old logic.
        # The run might succeed (using old VM) or fail (if old VM is broken), but our assertion
        # focuses solely on whether the NEW path was taken.
        
        # We wrap in try/except because running the OLD vm logic might trigger unrelated errors
        # depending on the environment, but we only care about the spy.
        try:
            await engine.run(workflow, use_vm=True)
        except Exception:
            # We ignore execution errors, we just want to know if the new compiler was invoked.
            pass
        
        # This assertion MUST FAIL for the test to be valid in the RED stage.
        mock_frontend_compile.assert_called_once()