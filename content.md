Excellent, we've narrowed it down to just 3 failures. This is the final refinement stage. The analysis of these errors points to subtle issues in the test suite itself, not the core logic, which is a very positive sign.

## [WIP] fix(tests): Correct final test failures in VM and Stdlib

### 错误分析

我们已成功将失败的测试数量减少到 3 个。对剩余错误的深入分析表明，这些问题源于测试用例的实现细节，而不是我们核心重构逻辑中的缺陷：

1.  **`TimeoutError` in `test_is_idle_state_changes`**:
    *   **根本原因**: 测试用例创建了一个 `ComputeRequest`，但没有提供 `sync_add` 函数所需的任何参数 (`input_args` 和 `input_kwargs` 都是空的)。这导致 `SignatureBinder` 在调用执行器 *之前* 就正确地抛出了一个 `TypeError`。
    *   **连锁反应**: 由于绑定失败，被 mock 的 `blocking_executor` 从未被调用，因此 `in_flight_event.set()` 也从未执行。测试的主线程因此在 `await in_flight_event.wait()` 处无限等待，最终超时。

2.  **`AttributeError` in `test_standard_launcher_dispatches_request`**:
    *   **根本原因**: 在上一步的修复中，我错误地修改了测试用例，让它手动创建了一个 `IOWrapper` 对象并传递给 `standard_launcher` 的*未装饰*版本。这是不正确的。
    *   **正确用法**: `@implements` 装饰器是一个黑盒，它负责接收一个简单的 `inputs` 字典并*在内部*创建 `IOWrapper`。测试应该与 `standard_launcher` 的公共 API（即被装饰后的函数）交互，直接向其传递一个 `inputs` 字典。

3.  **`NameError` in `test_standard_launcher_emits_observability_event`**:
    *   **根本原因**: 这是一个简单的疏忽。在上一步修改该测试时，忘记了添加对 `LauncherSpec` 的导入。

### 用户需求

修复最后 3 个失败的测试，以完成整个重构和验证过程。

### 评论

这最后的一组失败非常有价值，它们暴露了测试与实现之间存在的细微契约不匹配。修复它们不仅能让我们的测试套件 100% 通过，还能提高测试代码本身的质量和正确性，使其成为新架构的可靠守护者。

### 目标

1.  在 `test_is_idle_state_changes` 中为 `ComputeRequest` 提供有效的参数，以确保它能通过参数绑定阶段。
2.  重构 `test_standard_launcher_dispatches_request`，移除手动的 `IOWrapper` 创建，并直接向 `standard_launcher` 传递一个 `inputs` 字典。
3.  在 `test_launcher.py` 中添加缺失的 `LauncherSpec` 导入。

### 基本原理

我们将通过精确的、小范围的修改来纠正这些测试用例中的逻辑错误。
*   对于 `TimeoutError`，我们通过提供有效的负载来满足 `SignatureBinder` 的契约，让测试流程能够继续进行。
*   对于 `AttributeError` 和 `NameError`，我们通过遵循 `@implements` 装饰器的正确使用模式并补全导入来纠正测试的设置代码。

这些修复将完成我们路线图的最后一步，为最终的提交扫清道路。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #comp/std #scope/core #ai/instruct #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 VM 集成测试 (`test_is_idle_state_changes`)

我们将为 `ComputeRequest` 提供有效的参数，以避免参数绑定失败。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
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

#### Acts 2: 修复标准库单元测试 (`test_launcher.py`)

我们将纠正对 `standard_launcher` 的测试方式，并添加缺失的导入。

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
~~~~~
~~~~~python.new
def test_standard_launcher_dispatches_request():
    from cascade.spec.specs.dyad import LauncherSpec

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

    # Execute the decorated function directly
    standard_launcher(inputs, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/dyad/test_launcher.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
def test_standard_launcher_emits_observability_event():
    from cascade.spec.specs.dyad import LauncherSpec

    node = create_mock_launcher_node({"obs_output": PortRole.OBSERVABILITY})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    from cascade.spec.physics.binding import implements
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    # The decorated function is what we should test
    decorated_launcher = implements(LauncherSpec)(raw_launcher)

    outputs = decorated_launcher({}, node, resources)

    assert "obs_output" in outputs
~~~~~

### 下一步建议

我们已经解决了最后几个已知的故障点。现在，请最终运行一次 `pytest`。我预计所有测试都将成功通过。

成功后，我们就可以满怀信心地将这个庞大而重要的重构作为一个原子提交，为 Cascade 的核心架构翻开崭新的一页。
