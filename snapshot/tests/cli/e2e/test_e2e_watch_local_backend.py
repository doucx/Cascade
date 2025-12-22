import asyncio
import json
import sys
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.connectors.local import LocalConnector
from cascade.runtime.subscribers import TelemetrySubscriber

# We import the internal logic from observer to test real-world behavior


@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not supported on Windows")
@pytest.mark.asyncio
async def test_watch_local_uds_e2e(tmp_path, monkeypatch):
    """
    End-to-end test for the local UDS telemetry loop.
    Engine -> LocalConnector -> UDS Server -> UDS Client -> on_message
    """
    db_path = tmp_path / "control.db"
    uds_path = str(tmp_path / "telemetry.sock")

    # 1. Setup Captured Events list
    received_events = []

    async def mocked_on_message(topic, payload):
        # Flatten the events for easy assertion
        body = payload.get("body", {})
        if body.get("type") == "LifecycleEvent":
            received_events.append(body.get("event"))
        elif body.get("type") == "TaskStateEvent":
            received_events.append(f"{body.get('task_name')}:{body.get('state')}")

    # Use monkeypatch to redirect observer's on_message to our collector
    monkeypatch.setattr("cascade.cli.observer.app.on_message", mocked_on_message)

    # 2. Configure Engine with LocalConnector
    event_bus = MessageBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )

    # We must attach and REGISTER the TelemetrySubscriber so the engine manages its lifecycle
    subscriber = TelemetrySubscriber(event_bus, connector)
    engine.add_subscriber(subscriber)

    # 3. Define a simple workflow
    @cs.task
    def hello():
        return "world"

    # 4. Start UDS Client (Watcher) in background
    async def run_client():
        # Retry logic similar to observer app
        attempts = 0
        while attempts < 5:
            try:
                reader, writer = await asyncio.open_unix_connection(uds_path)
                while not reader.at_eof():
                    line = await reader.readline()
                    if not line:
                        break
                    data = json.loads(line)
                    await mocked_on_message("uds", data)
                writer.close()
                await writer.wait_closed()
                break
            except (ConnectionRefusedError, FileNotFoundError):
                await asyncio.sleep(0.1)
                attempts += 1

    client_task = asyncio.create_task(run_client())

    # 5. Run Engine
    await engine.run(hello())

    # Give a small buffer for the final UDS messages to be flushed and read
    await asyncio.sleep(0.2)
    client_task.cancel()

    # 6. Assertions
    # Expected sequence:
    # - ENGINE_STARTED
    # - hello:RUNNING
    # - hello:COMPLETED
    # - ENGINE_STOPPED

    assert "ENGINE_STARTED" in received_events
    assert "hello:RUNNING" in received_events
    assert "hello:COMPLETED" in received_events
    assert "ENGINE_STOPPED" in received_events
