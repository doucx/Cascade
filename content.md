You are absolutely right. A feature this critical needs robust regression tests to prevent it from breaking again. The test failures you've uncovered are a direct result of our recent fixes; the tests themselves are now out of sync with the corrected behavior.

This is a healthy and necessary step: we must update the tests to reflect the new, correct reality. I will generate a plan to fix these broken tests.

## [WIP] test: Add regression tests for constraint system and fix related test failures

### 錯誤分析

你提供的测试失败报告非常清晰，揭示了两组独立的问题，都源于测试代码与生产代码的实现细节不再匹配。

#### 1. `tests/cli-observer` 失败：载荷协议不匹配 (Payload Schema Mismatch)

*   **根本原因**: 我们在上一个计划中修复了 `cs-observer` 的载荷解析逻辑，将其从需要嵌套的 `header` 对象（`{ "header": { "run_id": ... } }`）改为了更简洁的扁平结构（`{ "run_id": ..., "body": ... }`）。然而，`test_observer_app.py` 中的测试用例仍然在构造**旧的、嵌套格式的**测试数据。
*   **症状**: 当测试调用 `observer_app.on_message` 时，`run_id = payload.get("run_id")` 这一行代码返回 `None`，导致函数提前退出，因此所有对 `mock_messaging_bus.info` 的预期调用都从未发生，从而引发断言错误。

#### 2. `tests/py/runtime` 失败：模拟行为不匹配 (Mock Behavior Mismatch)

*   **根本原因**: 我们修复了 `Engine` 处理 `resume` 命令的逻辑，将其判断条件从 `if not payload:` 更改为 `if payload == {}:`。这是因为真实的 `MqttConnector` 会将一个空的 MQTT 消息（`resume` 命令的信号）解析为一个**空字典 `{}`**。
*   **症状**: 在 `test_engine_pauses_and_resumes_specific_task` 测试中，我们通过 `await mock_connector._trigger_message(..., "")` 来模拟 `resume` 命令。这个测试专用的 `MockConnector` 直接将**空字符串 `""`** 传递给了 `Engine` 的回调。`Engine` 的新逻辑收到了 `""`，与期望的 `{}` 不匹配，因此 `resume` 逻辑从未被触发，导致工作流永久暂停，测试最终超时。

### 用户需求
1.  修复所有因近期代码变更而失败的测试用例。
2.  确保新的测试能够作为有效的回归测试，保证 `pause`/`resume` 功能的健壮性。

### 评论
这是一个非常好的实践。测试套件是项目的免疫系统，当实现发生变化时，更新测试以反映新的行为契约是至关重要的。这确保了我们的安全网是可靠的，并且未来的重构不会无意中破坏我们已经修复的功能。

### 目标
1.  更新 `tests/cli-observer/test_observer_app.py` 中的所有测试用例，使其构造的遥测事件 `payload` 符合新的扁平化协议。
2.  更新 `tests/py/runtime/test_engine_constraints.py` 中的 `resume` 测试，使其模拟 `MockConnector` 发送一个空字典 `{}` 而不是空字符串 `""`，以准确反映真实组件的行为。

### 基本原理
测试即代码。当一个组件的公开契约或其依赖项的行为发生变化时，验证该组件的测试代码也必须同步演进。本次修复遵循这一原则，通过对齐测试中的数据结构和模拟行为，恢复测试套件的健康状态，并为新功能建立起有效的回归防护。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/cli #comp/runtime #task/domain/testing #task/object/regression-suite #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 `cs-observer` 测试中的载荷结构

我们将逐一修改 `test_observer_app.py` 中所有使用旧 `header` 结构的 `payload`。

~~~~~act
patch_file
tests/cli-observer/test_observer_app.py
~~~~~
~~~~~python
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "RUNNING",
            "task_name": "process_data",
        },
    }
~~~~~
~~~~~python
    payload = {
        "run_id": "run-123",
        "body": {
            "type": "TaskStateEvent",
            "state": "RUNNING",
            "task_name": "process_data",
        },
    }
~~~~~

~~~~~act
patch_file
tests/cli-observer/test_observer_app.py
~~~~~
~~~~~python
    payload = {
        "header": {"run_id": "run-123"},
        "body": {
            "type": "TaskStateEvent",
            "state": "COMPLETED",
            "task_name": "generate_report",
            "duration_ms": 123.45,
        },
    }
~~~~~
~~~~~python
    payload = {
        "run_id": "run-123",
        "body": {
            "type": "TaskStateEvent",
            "state": "COMPLETED",
            "task_name": "generate_report",
            "duration_ms": 123.45,
        },
    }
~~~~~

~~~~~act
patch_file
tests/cli-observer/test_observer_app.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    payload = {
        "run_id": "run-123",
        "body": {
            "type": "TaskStateEvent",
            "state": "FAILED",
            "task_name": "api_call",
            "duration_ms": 50.0,
            "error": "TimeoutError",
        },
    }
~~~~~

~~~~~act
patch_file
tests/cli-observer/test_observer_app.py
~~~~~
~~~~~python
    payload1 = {
        "header": {"run_id": "run-abc"},
        "body": {"type": "LifecycleEvent", "event": "ENGINE_STARTED"},
    }
    payload2 = {
        "header": {"run_id": "run-abc"},
        "body": {"type": "TaskStateEvent", "state": "RUNNING", "task_name": "task1"},
    }
~~~~~
~~~~~python
    payload1 = {
        "run_id": "run-abc",
        "body": {"type": "LifecycleEvent", "event": "ENGINE_STARTED"},
    }
    payload2 = {
        "run_id": "run-abc",
        "body": {"type": "TaskStateEvent", "state": "RUNNING", "task_name": "task1"},
    }
~~~~~

#### Acts 2: 修复 `engine_constraints` 测试中的 `resume` 模拟

现在，我们修复 `test_engine_pauses_and_resumes_specific_task` 测试，使其发送正确的 `resume` 载荷。

~~~~~act
patch_file
tests/py/runtime/test_engine_constraints.py
~~~~~
~~~~~python
    # 6. Inject a RESUME command for 'task_b'
    # An empty payload on a retained topic clears the constraint.
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", ""
    )
~~~~~
~~~~~python
    # 6. Inject a RESUME command for 'task_b'
    # An empty payload on a retained topic clears the constraint. The connector
    # translates this to an empty dictionary.
    await mock_connector._trigger_message(
        f"cascade/constraints/{pause_scope.replace(':', '/')}", {}
    )
~~~~~

### 下一步建议
我们已经修复了所有已知的测试失败。现在，我们应该将这些测试修复与之前的业务逻辑修复合并到一个原子提交中。

1.  请重新运行完整的测试套件，确认所有测试现在都已通过。
2.  确认通过后，我们可以生成一个 `[COMMIT]` 计划，将 `engine.py`, `connector.py` 以及这两个测试文件的修改一起提交。
