import pytest
from cascade.adapters.state.in_memory import InMemoryStateBackend


@pytest.mark.asyncio
async def test_in_memory_functional():
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
