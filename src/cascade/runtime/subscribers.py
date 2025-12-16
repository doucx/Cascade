from .bus import MessageBus
from ..messaging.bus import bus as messaging_bus
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
)


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
        messaging_bus.info("run.started", target_tasks=event.target_tasks)
        if event.params:
            messaging_bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            messaging_bus.info("run.finished_success", duration=event.duration)
        else:
            messaging_bus.error("run.finished_failure", duration=event.duration, error=event.error)

    def on_task_started(self, event: TaskExecutionStarted):
        messaging_bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            messaging_bus.info("task.finished_success", task_name=event.task_name, duration=event.duration)
        else:
            messaging_bus.error("task.finished_failure", task_name=event.task_name, duration=event.duration, error=event.error)

    def on_task_skipped(self, event: TaskSkipped):
        messaging_bus.info("task.skipped", task_name=event.task_name, reason=event.reason)

    def on_task_retrying(self, event: TaskRetrying):
        messaging_bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error
        )
