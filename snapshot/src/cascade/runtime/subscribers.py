import sys
from typing import TextIO
from .bus import MessageBus
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
    Listens to events and prints user-friendly logs to a stream (default: stdout).
    """

    def __init__(self, bus: MessageBus, stream: TextIO = sys.stdout):
        self._stream = stream

        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        targets = ", ".join(event.target_tasks)
        self._print(f"▶️  Starting Run for targets: [{targets}]")
        if event.params:
            self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
        else:
            self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            self._print(
                f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s"
            )
        else:
            self._print(
                f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}"
            )

    def on_task_skipped(self, event: TaskSkipped):
        self._print(f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})")

    def on_task_retrying(self, event: TaskRetrying):
        self._print(
            f"  ⚠️  Retrying task `{event.task_name}` "
            f"(Attempt {event.attempt}/{event.max_attempts}) "
            f"in {event.delay:.2f}s... Error: {event.error}"
        )
