import pytest
from contextlib import ExitStack
from cascade.spec.dsl.task import task
from cascade.runtime.legacy.strategies.vm import VMExecutionStrategy
from cascade.spec.runtime import ExecutionContext
from cascade.runtime import EventBus

@task
def add(a: int, b: int) -> int:
    return a + b

@task
def square(n: int) -> int:
    return n * n

@pytest.mark.asyncio
async def test_vm_strategy_e2e_execution():
    # 1. Define workflow
    target = square(add(1, 2))

    # 2. Setup strategy and context
    # Use real EventBus for high-fidelity testing
    bus = EventBus()
    strategy = VMExecutionStrategy(bus=bus)

    mock_state_backend = None # VM Strategy doesn't use legacy state backend
    context = ExecutionContext(
        run_id="test-run-123",
        state_backend=mock_state_backend,
        run_stack=ExitStack(),
        active_resources={},
    )

    # 3. Execute
    result = await strategy.execute(target, context)

    # 4. Assert
    assert result == 9