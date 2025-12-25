import pytest
import asyncio
from unittest.mock import MagicMock

from cascade.runtime.events import TaskExecutionFinished
from cascade.runtime.subscribers import TelemetrySubscriber
from cascade.cli.observer.app import on_message
from cascade.testing import MockConnector


@pytest.mark.asyncio
async def test_telemetry_subscriber_to_observer_contract():
    """
    Verifies that the JSON produced by TelemetrySubscriber is correctly
    consumed by the cs-observer's on_message handler.
    """
    # 1. ARRANGE: Producer side
    connector = MockConnector()
    subscriber = TelemetrySubscriber(MagicMock(), connector)

    # 2. PRODUCE: Create a runtime event and have the subscriber process it
    event = TaskExecutionFinished(
        run_id="run-contract-test",
        task_id="task-abc",
        task_name="contract_task",
        status="Succeeded",
        duration=0.123,
    )
    subscriber.on_event(event)

    # Let the asyncio.create_task in on_event run
    await asyncio.sleep(0.01)

    # 3. ASSERT: The payload was captured in the publish log
    assert len(connector.publish_log) == 1
    produced_payload = connector.publish_log[0]["payload"]

    assert produced_payload is not None
    assert produced_payload["run_id"] == "run-contract-test"
    assert produced_payload["body"]["task_name"] == "contract_task"

    # 4. ARRANGE: Consumer side
    mock_bus = MagicMock()

    # 5. CONSUME: Feed the produced JSON directly to the observer's handler
    # We patch the bus used by the observer to intercept the result
    observer_app_bus_path = "cascade.cli.observer.app.bus"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(observer_app_bus_path, mock_bus)
        await on_message("a/topic", produced_payload)

    # 6. ASSERT: The observer called the bus with the correct, parsed information
    mock_bus.info.assert_any_call(
        "observer.telemetry.task_state.COMPLETED",
        task_name="contract_task",
        duration_ms=123.0,
        error="",
    )