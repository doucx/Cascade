import pytest
import asyncio
from contextlib import ExitStack

import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.adapters.state import InMemoryStateBackend


@pytest.mark.asyncio
async def test_vm_strategy_executes_simplest_workflow():
    """
    A minimal, isolated integration test for VMExecutionStrategy.

    This test is designed to reproduce the deadlock scenario by directly invoking
    the strategy without the complexity of the full Engine.
    """

    # 1. Define the simplest possible workflow
    @cs.task
    def get_value():
        return 42

    workflow = get_value()

    # 2. Instantiate the strategy and its minimal dependencies
    strategy = VMExecutionStrategy(bus=MessageBus())
    state_backend = InMemoryStateBackend("test-run-vm-strategy")

    # 3. Execute the strategy with a timeout
    try:
        result = await asyncio.wait_for(
            strategy.execute(
                target=workflow,
                run_id="test-run-vm-strategy",
                params={},
                state_backend=state_backend,
                run_stack=ExitStack(),
                active_resources={},
            ),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        pytest.fail("The VMStrategy execution timed out, indicating a deadlock.")

    # 4. Assert the result
    assert result == 42