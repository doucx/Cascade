Excellent, the tests have correctly identified a flaw in our logic. This is exactly why we write them.

The error `AssertionError: Expected 'info' to be called once. Called 2 times` tells us that `bus.info` was called twice, but the test only expected a single call.

### 错误分析

The root cause is in the `on_message` callback. When it receives the *first* message for a new `run_id`, it performs two actions:
1.  It prints the run header: `bus.info("observer.telemetry.run_header", ...)`
2.  It prints the specific event message: `bus.info("observer.telemetry.task_state.RUNNING", ...)`

Our test assertion, `assert_called_once_with`, is too strict. It requires that the mock was called *exactly once* and with the specified arguments. Since there were two calls, the test failed on the call count.

Furthermore, the tests suffer from **state leakage**. The `seen_run_ids` set is a global variable, so whichever test runs first will add `"run-123"` to it, causing subsequent tests to behave differently. This is why only the first test failed. We must ensure each test runs in an isolated state.

### 解决方案

1.  **Isolate Test State**: We will add `observer_app.seen_run_ids.clear()` to the beginning of each test case to ensure that the global state is reset before each run. This makes the tests independent of execution order.
2.  **Refine Assertions**: Instead of asserting the total number of calls, we will use `assert_any_call`. This assertion specifically checks if a call with the given arguments was made at least once, regardless of other calls. This correctly reflects our intent: "Was the correct 'RUNNING' event message sent?".

## [WIP] fix(tests): Isolate test state and refine observer assertions

### 用户需求
修复 `cs-observer` 测试套件中的 `AssertionError`，并消除因共享全局状态 (`seen_run_ids`) 导致的测试间依赖。

### 评论
这是一个典型的测试驱动开发 (TDD) 循环的胜利。测试暴露了两个常见问题：过于严格的断言和测试间的状态泄漏。通过修正这些问题，我们将使测试套件更加健壮、可靠，并且与实现细节解耦。

### 目标
1.  在每个处理遥测事件的测试用例开始时，清空 `observer_app.seen_run_ids` 集合。
2.  将测试断言从 `assert_called_once_with` 修改为 `assert_any_call`，以准确验证“意图”的存在，而不是调用次数。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/cli #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复并加固 Observer 测试套件

我们将修改 `test_app.py` 中的所有测试用例，为它们添加状态重置逻辑，并使用更合适的断言。

~~~~~act
patch_file
tests/cli-observer/test_app.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_on_message_handles_task_running_event(mock_messaging_bus):
    """
    Verify that a 'RUNNING' TaskStateEvent is correctly parsed and rendered.
    """
    # Arrange: A sample telemetry payload
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "RUNNING",
            "task_name": "process_data",
        },
    }

    # Act: Directly call the callback function
    await observer_app.on_message("a/topic", payload)

    # Assert: Verify the bus was called with the correct semantic intent
    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.RUNNING",
        task_name="process_data",
        duration_ms=0,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_completed_event(mock_messaging_bus):
    """
    Verify that a 'COMPLETED' TaskStateEvent is correctly parsed.
    """
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "COMPLETED",
            "task_name": "generate_report",
            "duration_ms": 123.45,
        },
    }

    await observer_app.on_message("a/topic", payload)

    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.COMPLETED",
        task_name="generate_report",
        duration_ms=123.45,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_failed_event(mock_messaging_bus):
    """
    Verify that a 'FAILED' TaskStateEvent is correctly parsed.
    """
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "FAILED",
            "task_name": "api_call",
            "duration_ms": 50.0,
            "error": "TimeoutError",
        },
    }

    await observer_app.on_message("a/topic", payload)

    mock_messaging_bus.info.assert_called_once_with(
        "observer.telemetry.task_state.FAILED",
        task_name="api_call",
        duration_ms=50.0,
        error="TimeoutError",
    )
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_on_message_handles_task_running_event(mock_messaging_bus):
    """
    Verify that a 'RUNNING' TaskStateEvent is correctly parsed and rendered.
    """
    # Arrange: Reset global state and define payload
    observer_app.seen_run_ids.clear()
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "RUNNING",
            "task_name": "process_data",
        },
    }

    # Act: Directly call the callback function
    await observer_app.on_message("a/topic", payload)

    # Assert: Verify the bus was called with the correct semantic intent.
    # We use assert_any_call because the run header might also be printed.
    mock_messaging_bus.info.assert_any_call(
        "observer.telemetry.task_state.RUNNING",
        task_name="process_data",
        duration_ms=0,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_completed_event(mock_messaging_bus):
    """
    Verify that a 'COMPLETED' TaskStateEvent is correctly parsed.
    """
    # Arrange
    observer_app.seen_run_ids.clear()
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "COMPLETED",
            "task_name": "generate_report",
            "duration_ms": 123.45,
        },
    }

    # Act
    await observer_app.on_message("a/topic", payload)

    # Assert
    mock_messaging_bus.info.assert_any_call(
        "observer.telemetry.task_state.COMPLETED",
        task_name="generate_report",
        duration_ms=123.45,
        error="",
    )


@pytest.mark.asyncio
async def test_on_message_handles_task_failed_event(mock_messaging_bus):
    """
    Verify that a 'FAILED' TaskStateEvent is correctly parsed.
    """
    # Arrange
    observer_app.seen_run_ids.clear()
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "FAILED",
            "task_name": "api_call",
            "duration_ms": 50.0,
            "error": "TimeoutError",
        },
    }

    # Act
    await observer_app.on_message("a/topic", payload)

    # Assert
    mock_messaging_bus.info.assert_any_call(
        "observer.telemetry.task_state.FAILED",
        task_name="api_call",
        duration_ms=50.0,
        error="TimeoutError",
    )
~~~~~
