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


LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stderr).
    """

    def __init__(
        self, bus: MessageBus, stream: TextIO = sys.stderr, min_level: str = "INFO"
    ):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level, 20) >= self._min_level_val

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        if self._should_log("INFO"):
            targets = ", ".join(event.target_tasks)
            self._print(f"▶️  Starting Run for targets: [{targets}]")
            if event.params:
                self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
            else:
                self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        if self._should_log("INFO"):
            self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(
                    f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s"
                )
            else:
                self._print(
                    f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}"
                )

    def on_task_skipped(self, event: TaskSkipped):
        if self._should_log("INFO"):
            self._print(
                f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})"
            )

    def on_task_retrying(self, event: TaskRetrying):
        if self._should_log("WARNING"):
            self._print(
                f"  ⚠️  Retrying task `{event.task_name}` "
                f"(Attempt {event.attempt}/{event.max_attempts}) "
                f"in {event.delay:.2f}s... Error: {event.error}"
            )
