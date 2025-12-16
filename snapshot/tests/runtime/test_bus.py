import io
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber


def test_message_bus_dispatch(bus_and_spy):
    """
    Tests that the bus correctly dispatches events to specifically subscribed handlers.
    """
    bus, spy = bus_and_spy

    specific_received = []

    def specific_handler(event: RunStarted):
        specific_received.append(event)

    bus.subscribe(RunStarted, specific_handler)

    # Publish relevant event
    event1 = RunStarted()
    bus.publish(event1)

    # Assert specific handler was called
    assert len(specific_received) == 1

    # Publish irrelevant event
    event2 = TaskExecutionFinished()
    bus.publish(event2)

    # Assert specific handler was NOT called again
    assert len(specific_received) == 1

    # Assert that the spy (wildcard) received everything
    assert len(spy.events) == 2
    assert spy.events[0] == event1
    assert spy.events[1] == event2


def test_message_bus_wildcard(bus_and_spy):
    """
    Tests that a wildcard subscriber (listening to base Event) receives all events.
    """
    bus, spy = bus_and_spy

    bus.publish(RunStarted(target_tasks=[], params={}))
    bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t", status="OK", duration=0.0)
    )

    assert len(spy.events) == 2
    assert isinstance(spy.events_of_type(RunStarted)[0], RunStarted)
    assert isinstance(spy.events_of_type(TaskExecutionFinished)[0], TaskExecutionFinished)


def test_human_readable_subscriber_output_formatting(bus_and_spy):
    """
    Tests that the subscriber correctly formats and prints different events.
    This test focuses on the subscriber's presentation logic.
    """
    bus, _ = bus_and_spy  # Spy is not used here, but fixture provides bus
    output = io.StringIO()
    HumanReadableLogSubscriber(bus, stream=output)

    # Simulate a flow of events
    bus.publish(RunStarted(target_tasks=["deploy"], params={"env": "prod"}))
    bus.publish(
        TaskExecutionFinished(
            task_id="123", task_name="build_image", status="Succeeded", duration=1.23
        )
    )
    bus.publish(
        TaskExecutionFinished(
            task_id="124",
            task_name="deploy_k8s",
            status="Failed",
            duration=0.05,
            error="AuthError",
        )
    )

    logs = output.getvalue()

    # Assertions are now less brittle, checking for key semantic markers
    assert "▶️" in logs
    assert "deploy" in logs
    assert "env" in logs
    assert "prod" in logs

    assert "✅" in logs
    assert "build_image" in logs

    assert "❌" in logs
    assert "deploy_k8s" in logs
    assert "AuthError" in logs


def test_human_readable_subscriber_log_level(bus_and_spy):
    """
    Tests that setting min_level correctly suppresses lower priority logs.
    """
    bus, _ = bus_and_spy
    output = io.StringIO()
    # Set level to ERROR, so INFO logs from RunStarted and Succeeded should be skipped
    HumanReadableLogSubscriber(bus, stream=output, min_level="ERROR")

    # INFO event
    bus.publish(RunStarted(target_tasks=["t1"]))
    # INFO event
    bus.publish(
        TaskExecutionFinished(
            task_id="1", task_name="t1", status="Succeeded", duration=0.1
        )
    )
    # ERROR event
    bus.publish(
        TaskExecutionFinished(
            task_id="2", task_name="t2", status="Failed", error="Boom", duration=0.1
        )
    )

    logs = output.getvalue()

    # Should NOT contain INFO-level markers
    assert "▶️" not in logs
    assert "✅" not in logs
    # Should contain ERROR-level markers
    assert "❌" in logs
    assert "Boom" in logs