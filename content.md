Excellent. The test run provides exactly the feedback we need. This is not a setback; it's the expected and necessary outcome of a major API refactoring. The errors confirm that our changes to the core spec have been successfully applied, and now we must align the surrounding test suite with the new reality.

The analysis is clear:
1.  **API Breakage in Tests**: The majority of failures are `TypeError` or `AttributeError` because the tests themselves are still creating `NodeIR` and `ComputeRequest` objects using the old, now-defunct `inputs` and `input_refs` fields. This is a validation that our core change worked.
2.  **Behavioral Mismatches**: A few tests fail on assertions (`test_graph_purity`, `test_sovereign_wiring`) because our refactor correctly changed the physical graph's structure (e.g., constant node names, port names). The tests were brittle and asserting against old implementation details.
3.  **A Missed File**: The logs reveal a crucial oversight: `cascade-vm/src/cascade/vm/compute/service.py` (`LocalComputeService`) was not updated alongside its counterpart, `BridgedComputeService`. This single omission is the root cause of all the high-level integration test failures that show an `AttributeError` in their logs.

We are now in **Stage 4: Validation and Consolidation**. I will generate a single, comprehensive plan to fix all these test-related issues and the missed implementation file.

## [WIP] fix(tests): Align test suite and VM with args/kwargs API

### 错误分析

我们的大规模重构取得了显著进展，将失败的测试从 77 个减少到了 17 个。剩余的失败是预料之中的，可分为三类：

1.  **测试代码中的直接 API 不匹配**：大量的测试（例如 `test_builder.py`, `test_generator.py`, `test_compute_adapters.py`）仍然在使用已被废弃的 `NodeIR(inputs=...)` 和 `ComputeRequest(input_refs=...)` 签名来构造测试数据，导致了 `TypeError` 和 `AttributeError`。这证明了我们的核心 API 变更已成功应用。

2.  **测试断言中的行为不匹配**：
    *   在 `test_graph_purity.py` 中，断言失败是因为它在寻找名为 `Const(a)` 的节点。我们的重构使命名逻辑更加健壮和确定，现在根据参数的位置索引命名，因此新名称是 `Const(0)`。
    *   在 `test_sovereign_wiring.py` 中，断言失败是因为它期望到 `consumer` 的连接端口名为 `msg`。根据新逻辑，物理端口名必须与逻辑参数身份（位置 0）同构，因此新端口名是 `0`。

3.  **遗漏的实现文件**：日志清楚地显示，所有高级集成测试（`test_machine_integration`, `test_ref_architecture` 等）的失败都源于 `cascade-vm/src/cascade/vm/compute/service.py` 中的 `LocalComputeService`。我们更新了 `BridgedComputeService`，但忘记了同步更新这个本地实现，导致它在处理新的 `ComputeRequest` 格式时崩溃。

### 用户需求

修复所有剩余的 17 个失败测试，完成“修复基础”路线图的第四阶段。这需要：
1.  更新所有测试用例，使其使用新的 `args`/`kwargs` API。
2.  修正那些对旧的、不正确的物理图结构进行断言的测试。
3.  修复被遗漏的 `LocalComputeService` 实现。

### 评论

这是重构的最后一步。通过修复这些测试，我们不仅可以验证我们核心改动的正确性，还可以将测试套件本身升级为新架构的“活文档”，确保未来的开发工作建立在正确、一致的契约之上。

### 目标

1.  修改所有使用旧 `NodeIR` 和 `ComputeRequest` 签名的测试文件。
2.  调整 `test_graph_purity` 和 `test_sovereign_wiring` 的断言以匹配新的、正确的物理图结构。
3.  修复 `LocalComputeService` 以正确处理新的 `ComputeRequest` 格式。

### 基本原理

我们的核心重构是成功的，但任何破坏性 API 变更都需要同步更新其依赖项，其中最重要的就是测试套件。本次修复是一个系统性的对齐过程：我们将所有测试用例和被遗漏的 `LocalComputeService` 与新的 `args`/`kwargs` 规约对齐。这将使我们的测试套件重新变绿，并为整个重构工作画上一个圆满的句号。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/vm #scope/core #ai/instruct #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复被遗漏的 VM 实现

首先修复最关键的生产代码 `LocalComputeService`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
    async def _process_request(self, request: ComputeRequest) -> None:
        # Note: self._active_count is incremented in run() before calling this
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)
~~~~~
~~~~~python.new
    async def _process_request(self, request: ComputeRequest) -> None:
        # Note: self._active_count is incremented in run() before calling this
        try:
            # 1. Resolve Inputs
            args = [self.store.get(ref) for ref in request.input_args]
            kwargs = {
                key: self.store.get(ref) for key, ref in request.input_kwargs.items()
            }

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
~~~~~
~~~~~python.new
    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # This method is now DEPRECATED due to the new ComputeRequest format
        # but we keep it to avoid breaking other potential internal usages,
        # though it's unlikely.
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
~~~~~

#### Acts 2: 修复编译器测试

更新编译器包内的单元和集成测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python.old
    # Check for the constant node for argument 'a' with value 1
    assert any(
        node.name == "Const(a)" and node.initial_payload == 1
        for node in nodes_collection
    ), "Constant node for value 1 not found after deserialization"

    # Check for the constant node for argument 'b' with value 2
    assert any(
        node.name == "Const(b)" and node.initial_payload == 2
        for node in nodes_collection
    ), "Constant node for value 2 not found after deserialization"
~~~~~
~~~~~python.new
    # Check for the constant node for argument '0' (was 'a') with value 1
    assert any(
        node.name == "Const(0)" and node.initial_payload == 1
        for node in nodes_collection
    ), "Constant node for value 1 not found after deserialization"

    # Check for the constant node for argument '1' (was 'b') with value 2
    assert any(
        node.name == "Const(1)" and node.initial_payload == 2
        for node in nodes_collection
    ), "Constant node for value 2 not found after deserialization"
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    node_1 = NodeIR(
        current_node_instance_hash="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        current_node_instance_hash="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )
~~~~~
~~~~~python.new
    node_1 = NodeIR(
        current_node_instance_hash="node_1",
        name="Task1",
        task=task_def,
        kwargs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        current_node_instance_hash="node_2",
        name="Task2",
        task=task_def,
        kwargs={"x": 20},
        constraints={"gpu": 1},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~
~~~~~python.old
    # That buffer should go to t2.launch
    t2_launch_id = f"{t2_id}.launch"
    inspector.assert_connection(d_dep_id, t2_launch_id, target_port="msg")
~~~~~
~~~~~python.new
    # That buffer should go to t2.launch
    t2_launch_id = f"{t2_id}.launch"
    # The port name is now the positional index '0', not the arg name 'msg'
    inspector.assert_connection(d_dep_id, t2_launch_id, target_port="0")
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    node_a = NodeIR(current_node_instance_hash="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        current_node_instance_hash="node_b",
        name="NodeB",
        task=task_b_def,
        inputs={"data": "node_a"},  # task_b.data comes from node_a
    )

    return GraphIR(nodes=[node_a, node_b])
~~~~~
~~~~~python.new
    node_a = NodeIR(current_node_instance_hash="node_a", name="NodeA", task=task_a_def)
    node_b = NodeIR(
        current_node_instance_hash="node_b",
        name="NodeB",
        task=task_b_def,
        kwargs={"data": "node_a"},  # task_b.data comes from node_a
    )

    return GraphIR(nodes=[node_a, node_b])
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.inputs == {"0": 1, "1": 2}
    assert node_ir.constraints == {}
~~~~~
~~~~~python.new
    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.args == [1, 2]
    assert node_ir.kwargs == {}
    assert node_ir.constraints == {}
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "process_data"
    assert node_ir.inputs == {"data": {"key": "value"}}
~~~~~
~~~~~python.new
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "process_data"
    assert node_ir.kwargs == {"data": {"key": "value"}}
    assert node_ir.args == []
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Verify upstream node is correct
    assert upstream_node.name == "add"
    assert upstream_node.inputs == {"0": 1, "1": 2}

    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.inputs == {
        "0": upstream_node.current_node_instance_hash,
        "1": 3,
    }
~~~~~
~~~~~python.new
    # Verify upstream node is correct
    assert upstream_node.name == "add"
    assert upstream_node.args == [1, 2]

    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.args == [
        upstream_node.current_node_instance_hash,
        3,
    ]
~~~~~

#### Acts 3: 修复标准库与 VM 测试 (Stdlib & VM)

最后，更新 `cascade-std` 和 `cascade-vm` 的测试。

~~~~~act
patch_file
packages/cascade-std/tests/unit/dyad/test_launcher.py
~~~~~
~~~~~python.old
def test_standard_launcher_dispatches_request():
    # Setup Inputs
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_launcher_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute
    standard_launcher(inputs, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]

    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_refs == {"arg1": "hello", "arg2": 123}
    assert "start_ts" in request.trace
~~~~~
~~~~~python.new
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
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/dyad/test_launcher.py
~~~~~
~~~~~python.old
    # Use IO capture (simulated by return value in test harness,
    # but strictly standard_launcher uses @implements which returns dict)
    # The @implements decorator logic wraps it, but for unit testing the inner function logic:
    # We need to simulate the IO wrapper if we were testing the inner logic directly,
    # OR we invoke the decorated function. standard_launcher IS the decorated function.

    outputs = standard_launcher({}, node, resources)

    assert "obs_output" in outputs
~~~~~
~~~~~python.new
    from cascade.spec.physics.binding import implements
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    # The decorated function is what we should test
    decorated_launcher = implements(LauncherSpec)(raw_launcher)

    outputs = decorated_launcher({}, node, resources)

    assert "obs_output" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash="sync_add_hash",
        input_refs={"0": ref1, "1": ref2},
        reply_to_nid="d_worker_out.node1",
        trace={"rid": "run1"},
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash="sync_add_hash",
        input_args=[ref1, ref2],
        input_kwargs={},
        reply_to_nid="d_worker_out.node1",
        trace={"rid": "run1"},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash="async_add_hash",
        input_refs={"a": ref_a, "b": ref_b},
        reply_to_nid="d_worker_out.node2",
        trace={},
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash="async_add_hash",
        input_args=[],
        input_kwargs={"a": ref_a, "b": ref_b},
        reply_to_nid="d_worker_out.node2",
        trace={},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash="compute_hash",
        input_refs={"x": store.put(10)},
        reply_to_nid="d_worker_out.node3",
        trace={},
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash="compute_hash",
        input_args=[],
        input_kwargs={"x": store.put(10)},
        reply_to_nid="d_worker_out.node3",
        trace={},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash="fail_hash",
        input_refs={"0": store.put(1), "1": store.put(1)},
        reply_to_nid="d_worker_out.node4",
        trace={},
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash="fail_hash",
        input_args=[store.put(1), store.put(1)],
        input_kwargs={},
        reply_to_nid="d_worker_out.node4",
        trace={},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_compute_adapters.py
~~~~~
~~~~~python.old
    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_refs={},
        reply_to_nid="d_out",
        trace={},
    )
~~~~~
~~~~~python.new
    request = ComputeRequest(
        code_hash="idle_test_hash",
        input_args=[],
        input_kwargs={},
        reply_to_nid="d_out",
        trace={},
    )
~~~~~
~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
    req = ComputeRequest(
        code_hash="slow_task",
        input_refs={"n": input_ref},  # Pass the argument correctly
        reply_to_nid="D_out",
        trace={},
    )
~~~~~
~~~~~python.new
    req = ComputeRequest(
        code_hash="slow_task",
        input_args=[],
        input_kwargs={"n": input_ref},  # Pass the argument correctly
        reply_to_nid="D_out",
        trace={},
    )
~~~~~

### 下一步建议

我们已经对测试套件和遗漏的实现文件进行了全面的修复和对齐。现在，我们真正处于了路线图的最后一步。

请再次运行 `pytest`。我非常有信心，这次所有的测试都将通过。

一旦测试全部通过，请告诉我，我将为您生成最终的 `[COMMIT]` 计划，将这项重大的架构改进作为一个原子提交，永久地载入项目的历史。
