You are right to push for a complete fix. The failures in the end-to-end tests reveal the final piece of the puzzle: the subscribers themselves were still implicitly coupled to the old contract, and one of the tests had a logical omission. My previous change correctly fixed the event *creation*, but now we must ensure the event *consumption* is equally robust and the tests are logically complete.

## [WIP] fix(e2e): Correct subscriber logic and complete E2E test assertions

### 错误分析

The remaining two failures stem from two distinct issues that were exposed by my previous refactoring:

1.  **`test_e2e_watch_local_backend.py`**: The `TelemetrySubscriber` incorrectly flags a successful task as `FAILED`. This is because its status check (`is EventState.SUCCEEDED`) is too strict. While the `EventState` enum is now used to create the event, some part of the event processing or transport layer (like JSON serialization in the `LocalConnector`) may be converting the `StrEnum` member to its primitive string value. Using a more lenient `==` comparison is idiomatic and correct for `StrEnum` and will fix this. The same issue affects `HumanReadableLogSubscriber`.
2.  **`test_end_to_end.py`**: The test itself is logically incomplete. It starts a two-step workflow (`greet(get_name())`) but only asserts that the first task (`get_name`) finished successfully, while omitting the assertion for the final `greet` task. This is a simple omission in the test's logic that needs to be corrected.

### 用户需求

To resolve the final E2E test failures by:
1.  Making the event subscriber logic robust to handle `StrEnum`'s string-like nature.
2.  Correcting the incomplete test logic in the E2E workflow test.

### 評論

This is the final cleanup step. By fixing the subscribers and the E2E test, we ensure that the "Concord" proposal is not only implemented but also correctly and fully validated by the highest level of testing, proving its resilience in a realistic execution environment.

### 目标

1.  Modify `HumanReadableLogSubscriber` and `TelemetrySubscriber` in `subscribers.py` to use `==` instead of `is` for `EventState` comparisons, making them robust.
2.  Add the missing `task.finished_success` assertion for the `greet` task in `test_end_to_end.py`.

### 基本原理

Using `==` with a `StrEnum` provides the best of both worlds: it allows for type-safe, semantic comparison against the enum member while also correctly comparing against the enum's underlying string value, should a conversion happen during serialization. This makes the consumers robust. Completing the assertions in the E2E test ensures our validation is as thorough as our implementation.

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/event-contracts #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Make Subscribers Robust

I will update both subscribers in `subscribers.py` to use the `==` operator for enum comparison.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
    def on_run_finished(self, event: RunFinished):
        if event.status is EventState.SUCCEEDED:
            bus.info("run.finished_success", duration=event.duration)
        else:
~~~~~
~~~~~python.new
    def on_run_finished(self, event: RunFinished):
        if event.status == EventState.SUCCEEDED:
            bus.info("run.finished_success", duration=event.duration)
        else:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status is EventState.SUCCEEDED:
            bus.info(
                "task.finished_success",
~~~~~
~~~~~python.new
    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == EventState.SUCCEEDED:
            bus.info(
                "task.finished_success",
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
~~~~~
~~~~~python.old
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", EventState.FAILED) is EventState.SUCCEEDED
                else "FAILED",
                TaskSkipped: "SKIPPED",
                TaskBlocked: "BLOCKED",
            }
~~~~~
~~~~~python.new
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED"
                if getattr(event, "status", EventState.FAILED) == EventState.SUCCEEDED
                else "FAILED",
                TaskSkipped: "SKIPPED",
                TaskBlocked: "BLOCKED",
            }
~~~~~

#### Acts 2: Complete E2E Test Logic

Finally, I will add the missing assertion to `test_end_to_end.py` to make the test logically complete.

~~~~~act
patch_file
tests/e2e/integration/test_end_to_end.py
~~~~~
~~~~~python.old
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
    mock_messaging_bus.info.assert_any_call(
        "task.finished_success", task_name="get_name", duration=pytest.approx(0, abs=1)
    )
    mock_messaging_bus.info.assert_any_call("task.started", task_name="greet")
    mock_messaging_bus.info.assert_any_call(
        "run.finished_success", duration=pytest.approx(0, abs=1)
    )
~~~~~
~~~~~python.new
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
    mock_messaging_bus.info.assert_any_call(
        "task.finished_success", task_name="get_name", duration=pytest.approx(0, abs=1)
    )
    mock_messaging_bus.info.assert_any_call("task.started", task_name="greet")
    mock_messaging_bus.info.assert_any_call(
        "task.finished_success", task_name="greet", duration=pytest.approx(0, abs=1)
    )
    mock_messaging_bus.info.assert_any_call(
        "run.finished_success", duration=pytest.approx(0, abs=1)
    )
~~~~~

### 下一步建议

We have now addressed all known failures and inconsistencies related to the event state contract. The implementation should be complete and correct.

Please run the full test suite one last time. If all tests pass, I will be ready to generate the final `[COMMIT]` plan to conclude this task.
