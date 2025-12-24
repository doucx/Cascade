import pytest
import asyncio
from unittest.mock import patch, ANY
from cascade.adapters.state.in_memory import InMemoryStateBackend


@pytest.mark.asyncio
async def test_in_memory_uses_to_thread():
    """
    Verifies that InMemoryStateBackend uses asyncio.to_thread for its operations,
    ensuring compliance with the non-blocking I/O contract even for dict operations.
    """
    backend = InMemoryStateBackend("test_run")

    # We patch asyncio.to_thread in the module where the backend is defined
    with patch("cascade.adapters.state.in_memory.asyncio.to_thread") as mock_to_thread:
        # We need to make the mock awaitable because the method awaits it
        async def async_mock(*args, **kwargs):
            return "mocked_result"

        mock_to_thread.side_effect = async_mock

        # Test put_result
        await backend.put_result("node_1", "data")
        mock_to_thread.assert_called_with(ANY, "node_1", "data")

        # Test get_result
        await backend.get_result("node_1")
        mock_to_thread.assert_called_with(ANY, "node_1")


@pytest.mark.asyncio
async def test_in_memory_functional():
    """
    Functional test to ensure it actually works as a backend.
    """
    backend = InMemoryStateBackend("test_run")

    # Put
    await backend.put_result("node_a", {"foo": "bar"})

    # Check
    assert await backend.has_result("node_a") is True
    assert await backend.has_result("node_b") is False

    # Get
    val = await backend.get_result("node_a")
    assert val == {"foo": "bar"}

    # Skip
    await backend.mark_skipped("node_b", "ConditionFalse")
    assert await backend.get_skip_reason("node_b") == "ConditionFalse"
    assert await backend.get_skip_reason("node_a") is None

    # Clear
    await backend.clear()
    assert await backend.has_result("node_a") is False
    assert await backend.get_skip_reason("node_b") is None