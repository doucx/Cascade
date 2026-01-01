import pytest
import asyncio
from unittest.mock import MagicMock

# These imports will fail initially, which is the point of TDD RED state
from cascade.vm.executors.physics import PhysicsExecutor
from cascade.spec.physics import FuncNode, Token
from cascade.vm.reactor.events import ExecutionFinished

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_reactor():
    """A mock reactor with a push_event method."""
    reactor = MagicMock()
    reactor.push_event = MagicMock()
    return reactor

@pytest.fixture
def mock_symbol_table():
    """A mock symbol table mapping node names to callables."""
    def sync_add(a, b):
        return a + b
    
    async def async_add(a, b):
        await asyncio.sleep(0)
        return a + b
        
    def sync_fail(a, b):
        raise ValueError("Sync failure")
        
    async def async_fail(a, b):
        raise ValueError("Async failure")

    return {
        "sync_add_hash": sync_add,
        "async_add_hash": async_add,
        "sync_fail_hash": sync_fail,
        "async_fail_hash": async_fail,
    }

# --- Test Cases ---

@pytest.mark.asyncio
async def test_physics_executor_submit_sync_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly find and execute a synchronous task,
    unpacking token payloads and pushing a successful ExecutionFinished event.
    """
    # 1. Setup
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="sync_add_hash") # Using name as hash for simplicity in test
    inputs = {
        "a": Token(payload=10),
        "b": Token(payload=20)
    }

    # 2. Action
    await executor.submit(node, inputs)

    # 3. Assertions
    # Verify that the reactor received the correct completion event
    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event, ExecutionFinished)
    assert event.node == node
    assert event.error is None
    
    # The result should be a new Token
    result_token = event.outputs.get("result")
    assert isinstance(result_token, Token)
    assert result_token.payload == 30
    assert result_token.tag == "default"


@pytest.mark.asyncio
async def test_physics_executor_submit_async_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly execute an asynchronous task.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="async_add_hash")
    inputs = {"a": Token(5), "b": Token(5)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]
    
    assert event.outputs["result"].payload == 10

@pytest.mark.asyncio
async def test_physics_executor_handles_sync_failure(mock_reactor, mock_symbol_table):
    """
    Tests that if a synchronous task fails, an ExecutionFinished event with an
    error is pushed to the reactor.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="sync_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event, ExecutionFinished)
    assert event.node == node
    assert isinstance(event.error, ValueError)
    assert str(event.error) == "Sync failure"
    assert not event.outputs # No output on failure

@pytest.mark.asyncio
async def test_physics_executor_handles_async_failure(mock_reactor, mock_symbol_table):
    """
    Tests failure handling for asynchronous tasks.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="async_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event.error, ValueError)
    assert str(event.error) == "Async failure"

@pytest.mark.asyncio
async def test_physics_executor_handles_missing_function(mock_reactor, mock_symbol_table):
    """
    Tests that a linking error (function not in symbol table) is reported.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="missing_hash")
    inputs = {}

    await executor.submit(node, inputs)
    
    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]
    
    assert isinstance(event.error, RuntimeError)
    assert "Linking failed" in str(event.error)