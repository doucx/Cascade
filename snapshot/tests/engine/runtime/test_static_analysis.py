import pytest
import cascade as cs
from unittest.mock import MagicMock
from cascade.runtime.engine import Engine


@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global message bus where it is used by subscribers."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)
    return mock_bus


@cs.task
def another_task():
    return "dependency"


@cs.task
def heavy_recursive_task(n: int, dep=None):
    if n <= 0:
        return "done"
    # ANTI-PATTERN: Recursive call with another task as argument
    return heavy_recursive_task(n - 1, dep=another_task())


@cs.task
def simple_recursive_task(n: int):
    if n <= 0:
        return "done"
    # OKAY: Recursive call with only literals or simple variables
    return simple_recursive_task(n - 1)


@pytest.mark.asyncio
async def test_dynamic_recursion_emits_warning(
    engine: Engine, mock_messaging_bus: MagicMock
):
    """
    Verifies that the dynamic recursion anti-pattern triggers a static analysis warning.
    """
    workflow = heavy_recursive_task(2)
    await engine.run(workflow)

    expected_message = (
        "Task 'heavy_recursive_task' uses a dynamic recursion pattern (calling other "
        "tasks in its arguments) which disables TCO optimizations, "
        "leading to significant performance degradation."
    )

    mock_messaging_bus.warning.assert_called_once_with(
        "graph.analysis.warning",
        task_name="heavy_recursive_task",
        warning_code="CS-W001",
        message=expected_message,
    )


@pytest.mark.asyncio
async def test_simple_recursion_does_not_warn(
    engine: Engine, mock_messaging_bus: MagicMock
):
    """
    Verifies that a standard, optimizable recursive task does NOT trigger a warning.
    """
    workflow = simple_recursive_task(2)
    await engine.run(workflow)

    mock_messaging_bus.warning.assert_not_called()