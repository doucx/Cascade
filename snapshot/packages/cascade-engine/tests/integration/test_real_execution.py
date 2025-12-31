import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus

@pytest.mark.asyncio
async def test_linear_workflow_with_vm():
    """
    Verifies that the new compiler pipeline can execute a real, 2-step workflow.
    This test is expected to FAIL initially because the Backend/VM does not yet
    handle function resolution or argument passing correctly.
    """
    # 1. Define tasks
    @cs.task
    def get_number() -> int:
        return 41

    @cs.task
    def add_one(x: int) -> int:
        return x + 1

    # 2. Build workflow
    workflow = add_one(get_number())

    # 3. Setup Engine with minimal dependencies
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 4. Run with VM enabled
    # We expect this to fail, likely inside the VM when it tries to call a function
    # that hasn't been resolved properly.
    result = await engine.run(workflow, use_vm=True)

    # 5. Assert final result
    assert result == 42