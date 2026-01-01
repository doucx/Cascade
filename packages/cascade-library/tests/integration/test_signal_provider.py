import asyncio
import time
import pytest
import cascade as cs

from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.connectors.local import LocalBusConnector


@pytest.fixture
def local_connector():
    return LocalBusConnector()


@pytest.fixture
def engine(local_connector):
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
        connector=local_connector,
    )


@pytest.mark.asyncio
async def test_recv_blocks_and_wakes_up(engine, local_connector):
    topic = "firefly/sync/pulse"
    payload = {"source": "firefly-01"}

    @cs.task
    def downstream_task(signal):
        return signal  # signal should be the received payload

    workflow = downstream_task(cs.recv(topic))

    # Run the engine in a background task
    engine_task = asyncio.create_task(engine.run(workflow))

    # Give the engine a moment to start and block on recv()
    await asyncio.sleep(0.05)
    assert not engine_task.done(), "Engine finished prematurely before signal was sent"

    # Publish the signal that should unblock the workflow
    await local_connector.publish(topic, payload)

    # Await the final result
    final_result = await asyncio.wait_for(engine_task, timeout=1.0)

    assert final_result == payload


@pytest.mark.asyncio
async def test_recv_times_out(engine):
    topic = "firefly/no-reply"
    timeout_duration = 0.05

    workflow = cs.recv(topic, timeout=timeout_duration)

    start_time = time.time()
    with pytest.raises(asyncio.TimeoutError):
        await engine.run(workflow)
    duration = time.time() - start_time

    # Verify that the timeout was respected
    assert timeout_duration <= duration < timeout_duration + 0.05, (
        f"Timeout was not respected. Expected ~{timeout_duration}s, took {duration:.2f}s."
    )
