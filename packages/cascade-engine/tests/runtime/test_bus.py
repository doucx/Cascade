import io
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.runtime.bus import MessageBus as EventBus
from cascade.common.messaging import bus as ui_bus
from cascade.common.renderers import CliRenderer


def test_message_bus_dispatch(bus_and_spy):
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
    bus, spy = bus_and_spy

    bus.publish(RunStarted(target_tasks=[], params={}))
    bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t", status="OK", duration=0.0)
    )

    assert len(spy.events) == 2
    assert isinstance(spy.events_of_type(RunStarted)[0], RunStarted)
    assert isinstance(
        spy.events_of_type(TaskExecutionFinished)[0], TaskExecutionFinished
    )


def test_human_readable_subscriber_integration():
    event_bus = EventBus()
    output = io.StringIO()
    # Use the global ui_bus store and inject a test renderer
    renderer = CliRenderer(store=ui_bus.store, stream=output, min_level="INFO")
    ui_bus.set_renderer(renderer)

    # Connect the subscriber to the event bus
    HumanReadableLogSubscriber(event_bus)

    # Publish events to the event bus
    event_bus.publish(RunStarted(target_tasks=["deploy"], params={"env": "prod"}))
    event_bus.publish(
        TaskExecutionFinished(
            task_id="123", task_name="build_image", status="Succeeded", duration=1.23
        )
    )
    event_bus.publish(
        TaskExecutionFinished(
            task_id="124",
            task_name="deploy_k8s",
            status="Failed",
            duration=0.05,
            error="AuthError",
        )
    )

    # Assert on the final rendered output
    logs = output.getvalue()
    # Note: icons might vary based on locales, but keys are stable.
    # We check for content that we know is in the message args.
    assert "deploy" in logs and "prod" in logs
    assert "build_image" in logs
    assert "deploy_k8s" in logs and "AuthError" in logs


def test_human_readable_subscriber_log_level_filtering():
    event_bus = EventBus()
    output = io.StringIO()
    # Set renderer level to ERROR
    renderer = CliRenderer(store=ui_bus.store, stream=output, min_level="ERROR")
    ui_bus.set_renderer(renderer)

    HumanReadableLogSubscriber(event_bus)

    # Publish INFO and ERROR level events
    event_bus.publish(RunStarted(target_tasks=["t1"]))  # INFO
    event_bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t1", status="Succeeded")
    )  # INFO
    event_bus.publish(
        TaskExecutionFinished(
            task_id="2", task_name="t2", status="Failed", error="Boom"
        )
    )  # ERROR

    logs = output.getvalue()

    # INFO messages should be filtered out
    assert "▶️" not in logs
    assert "✅" not in logs
    # ERROR messages should be present
    assert "❌" in logs
    assert "Boom" in logs
