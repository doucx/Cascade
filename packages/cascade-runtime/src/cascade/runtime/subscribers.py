import platform
import os
from datetime import datetime, timezone
from .bus import MessageBus
from cascade.common.messaging import bus
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    Event,
)
from cascade.interfaces.protocols import Connector


class HumanReadableLogSubscriber:
    """
    Listens to runtime events and translates them into semantic messages
    on the messaging bus. It acts as a bridge between the event domain
    and the user-facing message domain.
    """

    def __init__(self, event_bus: MessageBus):
        # Subscribe to relevant events from the core event_bus
        event_bus.subscribe(RunStarted, self.on_run_started)
        event_bus.subscribe(RunFinished, self.on_run_finished)
        event_bus.subscribe(TaskExecutionStarted, self.on_task_started)
        event_bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        event_bus.subscribe(TaskSkipped, self.on_task_skipped)
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)

    def on_run_started(self, event: RunStarted):
        bus.info("run.started", target_tasks=event.target_tasks)
        if event.params:
            bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            bus.info("run.finished_success", duration=event.duration)
        else:
            bus.error(
                "run.finished_failure", duration=event.duration, error=event.error
            )

    def on_task_started(self, event: TaskExecutionStarted):
        bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            bus.info(
                "task.finished_success",
                task_name=event.task_name,
                duration=event.duration,
            )
        else:
            bus.error(
                "task.finished_failure",
                task_name=event.task_name,
                duration=event.duration,
                error=event.error,
            )

    def on_task_skipped(self, event: TaskSkipped):
        bus.info(
            "task.skipped", task_name=event.task_name, reason=event.reason
        )

    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )


class TelemetrySubscriber:
    """
    Listens to runtime events and publishes them as structured telemetry
    data via a Connector.
    """

    def __init__(self, event_bus: MessageBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
        event_bus.subscribe(Event, self.on_event)

    def _create_header(self, run_id: str) -> dict:
        return {
            "v": "1.0",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "org_id": os.getenv("CASCADE_ORG_ID", "local"),
            "project_id": os.getenv("CASCADE_PROJECT_ID", "default"),
            "source": self._source_id,
        }

    async def on_event(self, event: Event):
        if not event.run_id:
            return

        payload = self._create_header(event.run_id)
        topic = f"cascade/telemetry/{payload['org_id']}/{payload['project_id']}/{event.run_id}/events"

        event_body = {}
        if isinstance(
            event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped)
        ):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if event.status == "Succeeded"
                else "FAILED",
                TaskSkipped: "SKIPPED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, "duration", 0) * 1000,
                "error": getattr(event, "error", None) or "",
            }

        elif isinstance(event, RunStarted):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STARTED"}

        elif isinstance(event, RunFinished):
            event_body = {"type": "LifecycleEvent", "event": "ENGINE_STOPPED"}

        # We can add more event types like ResourceEvent later

        if event_body:
            payload["body"] = event_body
            # Fire-and-forget publish
            asyncio.create_task(self._connector.publish(topic, payload))
