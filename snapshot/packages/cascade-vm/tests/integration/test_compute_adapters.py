import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from contextlib import ExitStack

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.object import Ref
from cascade.spec.runtime import ExecutionContext
from cascade.runtime.storage import InMemoryObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, BridgedComputeService
from cascade.spec.dsl.task import task


# --- Test Functions ---
def sync_add(a, b):
    return a + b


async def async_add(a, b):
    return a + b


@task(mode="compute")
def sync_compute_task(x):
    return x * x


# --- Fixtures ---


@pytest.fixture
def store():
    return InMemoryObjectStore()


@pytest.fixture
def registry():
    return CodeRegistry()


@pytest.fixture
def mock_executor():
    return AsyncMock()


@pytest.fixture
def inbound_queue():
    return asyncio.Queue()


@pytest.fixture
def outbound_queue():
    return asyncio.Queue()


@pytest.fixture
def wakeup_event():
    return asyncio.Event()


@pytest.fixture
def mock_context(store):
    return ExecutionContext(
        run_id="test-run",
        state_backend=Mock(),
        object_store=store,
        run_stack=ExitStack(),
        resource_container=Mock(),
    )


@pytest.fixture
def service(
    mock_executor,
    store,
    registry,
    inbound_queue,
    outbound_queue,
    wakeup_event,
    mock_context,
):
    return BridgedComputeService(
        executor=mock_executor,
        store=store,
        registry=registry,
        inbound_queue=inbound_queue,
        outbound_queue=outbound_queue,
        context=mock_context,
        wakeup_event=wakeup_event,
    )


@pytest.fixture
async def service_task(service):
    task = asyncio.create_task(service.run())
    yield task
    service.stop()
    # Give the service a moment to process the stop signal
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# --- Tests ---


@pytest.mark.asyncio
async def test_process_sync_task(
    service, service_task, store, registry, inbound_queue, outbound_queue, mock_executor
):
    # 1. Setup
    registry.register("sync_add_hash", sync_add)
    mock_executor.execute.return_value = 3

    ref1 = store.put(1)
    ref2 = store.put(2)
    request = ComputeRequest(
        code_hash="sync_add_hash",
        input_refs={"0": ref1, "1": ref2},
        reply_to_nid="d_worker_out.node1",
        trace={"rid": "run1"},
    )

    # 2. Act
    await inbound_queue.put(request)
    reply_nid, result_token = await asyncio.wait_for(outbound_queue.get(), timeout=1)

    # 3. Assert
    assert reply_nid == "d_worker_out.node1"
    assert isinstance(result_token, Token)
    assert isinstance(result_token.payload, Ref)
    assert result_token.trace == {"rid": "run1"}
    assert store.get(result_token.payload) == 3

    mock_executor.execute.assert_awaited_once()
    proxy_node = mock_executor.execute.await_args.args[0]
    assert proxy_node.name == "sync_add"
    assert proxy_node.definition.is_async is False
    assert proxy_node.definition.mode == "blocking"

    func = mock_executor.execute.await_args.args[1]
    assert func == sync_add

    args = mock_executor.execute.await_args.args[2]
    kwargs = mock_executor.execute.await_args.args[3]
    # SignatureBinder normalizes args to a tuple
    assert tuple(args) == (1, 2)
    assert kwargs == {}


@pytest.mark.asyncio
async def test_process_async_task(
    service, service_task, store, registry, inbound_queue, outbound_queue, mock_executor
):
    # 1. Setup
    registry.register("async_add_hash", async_add)
    mock_executor.execute.return_value = 5

    ref_a = store.put(2)
    ref_b = store.put(3)
    request = ComputeRequest(
        code_hash="async_add_hash",
        input_refs={"a": ref_a, "b": ref_b},
        reply_to_nid="d_worker_out.node2",
        trace={},
    )

    # 2. Act
    await inbound_queue.put(request)
    reply_nid, result_token = await asyncio.wait_for(outbound_queue.get(), timeout=1)

    # 3. Assert
    assert store.get(result_token.payload) == 5

    mock_executor.execute.assert_awaited_once()
    proxy_node = mock_executor.execute.await_args.args[0]
    assert proxy_node.definition.is_async is True  # Key assertion for this test
    assert proxy_node.definition.mode == "blocking"

    func = mock_executor.execute.await_args.args[1]
    assert func == async_add

    args = mock_executor.execute.await_args.args[2]
    kwargs = mock_executor.execute.await_args.args[3]
    # inspect.bind normalizes named arguments to positional if they match positional parameters
    assert tuple(args) == (2, 3)
    assert kwargs == {}


@pytest.mark.asyncio
async def test_task_with_compute_mode(
    service, service_task, store, registry, inbound_queue, outbound_queue, mock_executor
):
    registry.register("compute_hash", sync_compute_task)
    mock_executor.execute.return_value = 100

    request = ComputeRequest(
        code_hash="compute_hash",
        input_refs={"x": store.put(10)},
        reply_to_nid="d_worker_out.node3",
        trace={},
    )
    await inbound_queue.put(request)
    await asyncio.wait_for(outbound_queue.get(), timeout=1)

    mock_executor.execute.assert_awaited_once()
    proxy_node = mock_executor.execute.await_args.args[0]
    assert proxy_node.definition.is_async is False
    assert proxy_node.definition.mode == "compute"  # Key assertion


@pytest.mark.asyncio
async def test_execution_failure(
    service, service_task, store, registry, inbound_queue, outbound_queue, mock_executor
):
    # 1. Setup
    registry.register("fail_hash", sync_add)
    error = ValueError("Execution failed")
    mock_executor.execute.side_effect = error

    request = ComputeRequest(
        code_hash="fail_hash",
        input_refs={"0": store.put(1), "1": store.put(1)},
        reply_to_nid="d_worker_out.node4",
        trace={},
    )

    # 2. Act
    await inbound_queue.put(request)
    _, result_token = await asyncio.wait_for(outbound_queue.get(), timeout=1)

    # 3. Assert
    result_value = store.get(result_token.payload)
    assert isinstance(result_value, ValueError)
    assert str(result_value) == "Execution failed"


@pytest.mark.asyncio
async def test_is_idle_state_changes(
    service, service_task, inbound_queue, outbound_queue
):
    # 1. Initial state
    assert service.is_idle() is True

    # 2. After queuing, before processing
    # Use a mock that will block, allowing us to inspect the state
    in_flight_event = asyncio.Event()

    async def blocking_executor(*args, **kwargs):
        in_flight_event.set()
        await asyncio.sleep(0.1)

    service.executor.execute = blocking_executor
    service.registry.register("idle_test_hash", sync_add)

    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_refs={},
        reply_to_nid="d_out",
        trace={},
    )
    await inbound_queue.put(request)
    assert service.is_idle() is False

    # 3. While processing
    await asyncio.wait_for(in_flight_event.wait(), timeout=1)
    assert service.is_idle() is False
    assert service.active_count == 1

    # 4. After completion
    await asyncio.wait_for(outbound_queue.get(), timeout=0.2)
    assert service.is_idle() is True
    assert service.active_count == 0
