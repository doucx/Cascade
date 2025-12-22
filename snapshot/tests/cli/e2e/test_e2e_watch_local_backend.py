import asyncio
import json
import sys
import pytest
from pathlib import Path

import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.connectors.local.connector import LocalConnector

# Define the dummy UDS path for testing
TEST_UDS_PATH = "/tmp/cascade-test-telemetry.sock"


@pytest.mark.skipif(
    sys.platform == "win32", reason="Unix Domain Sockets are not supported on Windows"
)
@pytest.mark.asyncio
async def test_e2e_uds_telemetry_flow(tmp_path):
    """
    Verifies that an Engine using LocalConnector broadcasts telemetry over UDS,
    and a client can connect and receive these events in real-time.
    """
    # Use a temp path for the socket to avoid conflicts
    uds_path = str(tmp_path / "telemetry.sock")
    db_path = str(tmp_path / "control.db")

    # 1. Setup the Engine components
    connector = LocalConnector(db_path=db_path, telemetry_uds_path=uds_path)
    bus = MessageBus()
    # Attach the subscriber that pushes events to the connector
    TelemetrySubscriber(bus, connector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus,
        connector=connector,
    )

    # Define a simple workflow
    @cs.task
    def hello_task():
        return "world"

    workflow = hello_task()

    # Shared state to capture received messages
    received_messages = []

    # 2. Define the Client Logic (Simulating cs-observer watch)
    async def run_client():
        # Wait for the server socket to be created
        max_retries = 20
        for _ in range(max_retries):
            if Path(uds_path).exists():
                break
            await asyncio.sleep(0.05)
        else:
            raise TimeoutError("UDS socket was not created by Engine")

        try:
            reader, writer = await asyncio.open_unix_connection(uds_path)
            try:
                while not reader.at_eof():
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        data = json.loads(line)
                        received_messages.append(data)
                    except json.JSONDecodeError:
                        pass
            finally:
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            # It's possible the engine finishes and closes socket before we read everything,
            # or connection refused if we are too fast/slow.
            # In a test, we mostly care that we got *some* data.
            print(f"Client error: {e}")

    # 3. Run Engine and Client concurrently
    client_task = asyncio.create_task(run_client())
    
    # Run the engine (this is the 'server')
    # It will start UDS server on connect() and stop it on disconnect()
    await engine.run(workflow)

    # Wait a bit for client to drain any remaining buffer
    await asyncio.sleep(0.1)
    
    # Cancel client task if it's still waiting (e.g. strict loop)
    if not client_task.done():
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass

    # 4. Assertions
    # We expect at least:
    # - Lifecycle: ENGINE_STARTED
    # - TaskState: hello_task RUNNING
    # - TaskState: hello_task COMPLETED
    # - Lifecycle: ENGINE_STOPPED
    
    assert len(received_messages) >= 4

    types = [m.get("body", {}).get("type") for m in received_messages]
    assert "LifecycleEvent" in types
    assert "TaskStateEvent" in types

    events = [m.get("body", {}).get("event") for m in received_messages if m.get("body", {}).get("type") == "LifecycleEvent"]
    assert "ENGINE_STARTED" in events
    assert "ENGINE_STOPPED" in events

    task_states = [m.get("body", {}).get("state") for m in received_messages if m.get("body", {}).get("type") == "TaskStateEvent"]
    assert "RUNNING" in task_states
    assert "COMPLETED" in task_states