import io
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber


def test_message_bus_dispatch():
    bus = MessageBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    # Subscribe to specific event
    bus.subscribe(RunStarted, handler)

    # Publish relevant event
    event1 = RunStarted(target_tasks=["t1"], params={})
    bus.publish(event1)

    assert len(received_events) == 1
    assert received_events[0] == event1

    # Publish irrelevant event
    event2 = TaskExecutionFinished(
        task_id="1", task_name="t", status="Succeeded", duration=0.1
    )
    bus.publish(event2)

    # Handler should not receive it
    assert len(received_events) == 1


def test_message_bus_wildcard():
    bus = MessageBus()
    received_events = []

    def handler(event):
        received_events.append(event)

    # Subscribe to base Event (wildcard)
    bus.subscribe(Event, handler)

    bus.publish(RunStarted(target_tasks=[], params={}))
    bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t", status="OK", duration=0.0)
    )

    assert len(received_events) == 2


def test_human_readable_subscriber():
    bus = MessageBus()
    output = io.StringIO()
    HumanReadableLogSubscriber(bus, stream=output)

    # Simulate a flow
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

    assert "▶️  Starting Run" in logs
    assert "env': 'prod'" in logs
    assert "✅ Finished task `build_image` in 1.23s" in logs
    assert "❌ Failed task `deploy_k8s`" in logs
    assert "AuthError" in logs


def test_subscriber_log_level_filtering():
    """Test that setting min_level suppresses lower priority logs."""
    bus = MessageBus()
    output = io.StringIO()
    # Set level to ERROR, so INFO logs should be skipped
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

    # Should NOT contain INFO logs
    assert "Starting Run" not in logs
    assert "Finished task `t1`" not in logs
    # Should contain ERROR logs
    assert "Failed task `t2`" in logs
    assert "Boom" in logs
