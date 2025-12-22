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
from cascade.cli.observer.app import on_message


@pytest.mark.skipif(sys.platform == "win32", reason="UDS is not supported on Windows")
@pytest.mark.asyncio
async def test_watch_local_uds_e2e(tmp_path, monkeypatch):
    """
    End-to-end test for the local UDS telemetry loop, using explicit synchronization.
    Engine -> LocalConnector -> UDS Server -> UDS Client -> on_message
    """
    db_path = tmp_path / "control.db"
    uds_path = str(tmp_path / "telemetry.sock")

    # Synchronization primitive
    run_finished_event = asyncio.Event()

    # 1. Setup Captured Events list
    received_events = []

    async def mocked_on_message(topic, payload):
        # Flatten the events for easy assertion
        body = payload.get("body", {})
        if body.get("type") == "LifecycleEvent":
            event = body.get("event")
            received_events.append(event)
            if event == "ENGINE_STOPPED":
                run_finished_event.set()  # Signal that the final event was received
        elif body.get("type") == "TaskStateEvent":
            received_events.append(f"{body.get('task_name')}:{body.get('state')}")

    # Use monkeypatch to redirect observer's on_message to our collector
    # Note: We must patch the imported function where it is defined, but use the mock to control data capture.
    monkeypatch.setattr("cascade.cli.observer.app.on_message", mocked_on_message)

    # 2. Configure Engine with LocalConnector
    event_bus = MessageBus()
    connector = LocalConnector(db_path=str(db_path), telemetry_uds_path=uds_path)
    TelemetrySubscriber(event_bus, connector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=event_bus,
        connector=connector,
    )

    # 3. Define a simple workflow
    @cs.task
    def hello():
        return "world"

    # 4. Start UDS Client (Watcher) in background
    async def run_client():
        attempts = 0
        while attempts < 5:
            try:
                # Client attempts to connect
                reader, writer = await asyncio.open_unix_connection(uds_path)
                
                # Main read loop: blocks until data or EOF
                while True:
                    line = await reader.readline()
                    if not line:
                        break  # Server closed connection
                    try:
                        data = json.loads(line)
                        await mocked_on_message("uds", data)
                    except json.JSONDecodeError:
                        continue
                
                writer.close()
                await writer.wait_closed()
                break  # Exit the retry loop after connection closes

            except (ConnectionRefusedError, FileNotFoundError):
                await asyncio.sleep(0.1)
                attempts += 1
            except asyncio.CancelledError:
                break
        
    client_task = asyncio.create_task(run_client())

    # 5. Run Engine (start execution)
    engine_run_task = asyncio.create_task(engine.run(hello()))

    # 6. Synchronize: Wait for the final ENGINE_STOPPED message to be processed.
    try:
        await asyncio.wait_for(run_finished_event.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        # If timeout, it means the message was lost or the client task failed early.
        pytest.fail(
            f"Timed out waiting for ENGINE_STOPPED event ({5.0}s). Received: {received_events}"
        )

    # 7. Final Assertions
    # Ensure the engine task itself finished cleanly (should be very fast after unblocking)
    await asyncio.wait_for(engine_run_task, timeout=1.0)

    # Clean up client task if it hasn't exited already due to server shutdown
    if not client_task.done():
        client_task.cancel()

    assert "ENGINE_STARTED" in received_events
    assert "hello:RUNNING" in received_events
    assert "hello:COMPLETED" in received_events
    assert "ENGINE_STOPPED" in received_events