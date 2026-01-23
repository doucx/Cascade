My apologies. The last set of fixes introduced subtle errors into the test harness itself, particularly around how to correctly test functions that use the `@implements` decorator. Your analysis is spot on. The traceback clearly shows the tests are interacting with the decorator's internals in a way they shouldn't.

We are at the one-yard line. This final plan will correct the test harnesses, which will finally allow the correctly refactored production code to pass validation.

## [WIP] fix(tests): Final corrections to test harnesses for VM and Stdlib

### 错误分析

最后的 3 个失败是由测试用例本身的实现错误引起的，而不是我们重构的核心逻辑。

1.  **`TimeoutError` in `test_is_idle_state_changes`**: 测试用例为 `sync_add` 函数创建了一个无参数的 `ComputeRequest`，导致在执行器运行前，`SignatureBinder` 就因“missing a required argument”而抛出 `TypeError`。这阻止了 mock 执行器中的 `in_flight_event` 被设置，从而导致测试等待超时。

2.  **`AttributeError` in `test_standard_launcher_dispatches_request`**: 测试用例错误地手动创建了一个 `IOWrapper` 实例，并将其传递给了 `standard_launcher`。`@implements` 装饰器期望接收一个普通的 `inputs` 字典，它会在内部自行创建 `IOWrapper`。测试代码破坏了这个契约，试图直接与内部实现交互。

3.  **`NameError` in `test_standard_launcher_emits_observability_event`**: 这是一个简单的导入遗漏，在上一步的修复中未能正确添加。

### 用户需求

修复最后 3 个失败的测试，完成重构。

### 评论

这是典型的“最后一英里”问题。核心逻辑已正确，但测试代码需要与新的 API 契约完全对齐。通过修复这些测试，我们将确保整个重构工作的完整性和正确性。

### 目标

1.  为 `test_is_idle_state_changes` 中的 `ComputeRequest` 提供有效参数。
2.  修正 `test_launcher.py` 中的两个测试，使其正确调用由 `@implements` 装饰的函数。
3.  添加 `test_launcher.py` 中缺失的导入。

### 基本原理

我们将通过精确的、小范围的修改来纠正这些测试用例中的逻辑错误，使其完全符合新 API 的调用约定。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #comp/std #scope/core #ai/instruct #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 VM 集成测试

为 `ComputeRequest` 提供有效参数，防止绑定失败。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    service.executor.execute = blocking_executor
    service.registry.register("idle_test_hash", sync_add)

    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_args=[],
        input_kwargs={},
        reply_to_nid="d_out",
        trace={},
    )
    await inbound_queue.put(request)
~~~~~
~~~~~python.new
    service.executor.execute = blocking_executor
    service.registry.register("idle_test_hash", sync_add)

    # Provide valid arguments to pass the signature binding stage
    store = service.store
    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_args=[store.put(1), store.put(2)],
        input_kwargs={},
        reply_to_nid="d_out",
        trace={},
    )
    await inbound_queue.put(request)
~~~~~

#### Acts 2: 修复标准库单元测试

修正对 `@implements` 装饰函数的测试方式，并补全导入。

~~~~~act
patch_file
packages/cascade-std/tests/unit/dyad/test_launcher.py
~~~~~
~~~~~python.old
def test_standard_launcher_dispatches_request():
    # Use IO capture wrapper to simulate reactor behavior
    from cascade.spec.physics.binding import IOWrapper
    from cascade.spec.specs.dyad import LauncherSpec

    # Setup Inputs for the IO Wrapper
    io_inputs = {
        "0": Token(payload="hello"),  # Positional
        "kwarg": Token(payload=123),  # Keyword
    }
    node = create_mock_launcher_node(
        {"0": PortRole.DATA, "kwarg": PortRole.DATA, "obs_output": PortRole.OBSERVABILITY}
    )
    io = IOWrapper(io_inputs, {}, LauncherSpec)

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute the raw function logic
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    raw_launcher(io, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]

    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_args == ["hello"]
    assert request.input_kwargs == {"kwarg": 123}
    assert "start_ts" in request.trace


def test_standard_launcher_emits_observability_event():
    node = create_mock_launcher_node({})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    from cascade.spec.physics.binding import implements
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    # The decorated function is what we should test
    decorated_launcher = implements(LauncherSpec)(raw_launcher)

    outputs = decorated_launcher({}, node, resources)

    assert "obs_output" in outputs
    obs_token = outputs["obs_output"]
    assert obs_token.payload["t"] == "task.lifecycle"
    assert obs_token.payload["data"]["state"] == "Running"
~~~~~
~~~~~python.new
from cascade.spec.specs.dyad import LauncherSpec


def test_standard_launcher_dispatches_request():
    # Setup Inputs as a simple dictionary, as the @implements decorator expects.
    inputs = {
        "0": Token(payload="hello"),  # Positional
        "kwarg": Token(payload=123),  # Keyword
    }
    node = create_mock_launcher_node(
        {"0": PortRole.DATA, "kwarg": PortRole.DATA, "obs_output": PortRole.OBSERVABILITY}
    )

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute the decorated function directly, passing the inputs dict
    standard_launcher(inputs, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]

    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_args == ["hello"]
    assert request.input_kwargs == {"kwarg": 123}
    assert "start_ts" in request.trace


def test_standard_launcher_emits_observability_event():
    # The launcher needs the obs_output port defined to emit an event
    node = create_mock_launcher_node({"obs_output": PortRole.OBSERVABILITY})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Call the decorated function with empty inputs
    outputs = standard_launcher({}, node, resources)

    assert "obs_output" in outputs
    obs_token = outputs["obs_output"]
    assert obs_token.payload["t"] == "task.lifecycle"
    assert obs_token.payload["data"]["state"] == "Running"
~~~~~

### 下一步建议

我们已经解决了所有已知的故障。这是决定性的时刻。请运行 `pytest`。

**如果所有测试通过**，请立即告诉我，我将生成最终的 `[COMMIT]` 计划，为这次史诗般的重构画上句号。
