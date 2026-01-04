import pytest
from unittest.mock import MagicMock

from cascade.spec.task import task
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.strategies.base import ExecutionContext


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


@pytest.mark.asyncio
async def test_vm_strategy_e2e_execution():
    """
    Verifies the full Compile -> Link -> Execute pipeline.
    """
    # 1. Define workflow
    target = square(add(1, 2))

    # 2. Setup strategy and context
    mock_bus = MagicMock()
    strategy = VMExecutionStrategy(bus=mock_bus)
    context = ExecutionContext(active_resources={})

    # 3. Execute
    result = await strategy.execute(target, context)

    # 4. Assert
    assert result == 9