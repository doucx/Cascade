import pytest
import asyncio
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_vm_strategy_completes_single_node_workflow_and_returns():
    """
    This is the most basic test for VMExecutionStrategy.
    It verifies that the strategy can:
    1. Start the Reactor.
    2. Execute a single task.
    3. Detect completion.
    4. Stop the Reactor.
    5. Return the final result.

    Under the current flawed implementation, this test will hang indefinitely.
    """
    @cs.task
    def simple_task():
        return "SUCCESS"

    workflow = simple_task()

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We run this with a timeout to prevent the test suite from hanging forever.
    # The test will fail by raising TimeoutError, which is our expected RED state.
    try:
        result = await asyncio.wait_for(
            engine.run(workflow, use_vm=True),
            timeout=2.0
        )
        assert result == "SUCCESS"
    except asyncio.TimeoutError:
        pytest.fail("The VMExecutionStrategy hung and did not complete within the timeout.")