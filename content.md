当然。测试失败的 `TypeError` 表明，我们正在 `await` 一些已经被重构为同步 (`def`) 的函数。这是因为 `cascade-std` 库正在向“同步内核”的架构演进，但测试套件没有同步更新。

我将生成一个计划，首先将 `cascade-std` 中剩余的异步函数完全转换为同步函数，然后修复所有相关的测试，移除不必要的 `await` 和 `async` 声明，使整个标准库与其测试套件在架构上保持一致。

## [WIP] refactor(std): 将标准库 ICs 转换为同步函数并修复测试

### 用户需求

修复 `cascade-std` 测试套件中的 `TypeError` 失败。通过将所有标准库集成电路（ICs）及其测试完全同步化，来完成向“同步内核”架构的迁移。

### 评论

这是一个关键的架构统一性修复。测试失败明确地暴露了实现 (`def`) 与测试 (`await`) 之间的不匹配，这违反了“高保真工程”原则。通过这次全面的同步化重构，我们将彻底消除这种不一致性，确保 `cascade-std` 作为一个整体，严格遵循高性能、无上下文切换的同步内核设计哲学。

### 目标

1.  将 `cascade-std` 模块中所有剩余的 `async def` 函数重构为同步的 `def` 函数。
2.  更新 `cascade-std` 的整个测试套件，移除对这些函数不必要的 `await` 调用。
3.  移除测试函数签名中的 `async` 关键字和 `@pytest.mark.asyncio` 装饰器。
4.  确保在修改后，`cascade-std` 的所有测试都能通过。

### 基本原理

根据“架构 incorruptibility”和“Sync StdLib”原则，所有在物理内核中运行的标准库组件都必须是同步的，以消除 `asyncio` 事件循环带来的调度开销。当前的 `TypeError` 证明了代码库正处于一个不稳定的中间状态。本次重构将通过一次原子性的、全面的修改，强制实现代码与测试的完全同步，从而恢复架构的完整性和测试套件的可靠性。

### 标签

#intent/refine #flow/ready #priority/high #comp/std #comp/tests #scope/core #dx #ai/instruct #task/domain/architecture #task/object/synchronization #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 同步化 Probe ICs

我们将 `probe` 目录下的所有 `async` 函数转换为同步函数。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/context.py
~~~~~
~~~~~python.old
async def param_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def param_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/env.py
~~~~~
~~~~~python.old
async def env_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def env_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/pulse.py
~~~~~
~~~~~python.old
async def pulse_generator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def pulse_generator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~

#### Acts 2: 同步化 Resource ICs

同样，转换 `resource` 目录下的 `async` 函数。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
async def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
async def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~

#### Acts 3: 同步化 System ICs

转换 `system` 目录下的 `async` 函数。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
async def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
async def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~

#### Acts 4: 同步化 Triad ICs

最后，转换 `triad` 目录下的 `observer`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~
~~~~~python.new
def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
~~~~~

#### Acts 5: 更新 Probe Tests

现在，我们修复所有测试文件，移除 `async` 和 `await`。

~~~~~act
patch_file
packages/cascade-std/tests/unit/probe/test_context.py
~~~~~
~~~~~python.old
async def test_param_probe_lookups_value():
    inputs = {"name": Token(payload="db_url"), "trigger": Token(payload=None)}

    # Mock WorkflowContext
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = "sqlite:///:memory:"

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "sqlite:///:memory:"
    mock_ctx.get_value.assert_called_once_with("db_url")


async def test_param_probe_returns_none_if_missing():
    inputs = {"name": Token(payload="missing"), "trigger": Token(payload=None)}
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = None

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload is None
~~~~~
~~~~~python.new
def test_param_probe_lookups_value():
    inputs = {"name": Token(payload="db_url"), "trigger": Token(payload=None)}

    # Mock WorkflowContext
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = "sqlite:///:memory:"

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = param_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "sqlite:///:memory:"
    mock_ctx.get_value.assert_called_once_with("db_url")


def test_param_probe_returns_none_if_missing():
    inputs = {"name": Token(payload="missing"), "trigger": Token(payload=None)}
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = None

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = param_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload is None
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/probe/test_env.py
~~~~~
~~~~~python.old
async def test_env_probe_samples_os_environ():
    inputs = {"name": Token(payload="TEST_VAR")}

    with patch.dict(os.environ, {"TEST_VAR": "cascade_value"}):
        outputs = await env_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "cascade_value"


async def test_env_probe_returns_none_if_env_missing():
    inputs = {"name": Token(payload="NON_EXISTENT_VAR")}

    # Ensure it's not in environ
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]

    outputs = await env_probe(inputs, MagicMock(), MagicMock())
    assert outputs["out"].payload is None
~~~~~
~~~~~python.new
def test_env_probe_samples_os_environ():
    inputs = {"name": Token(payload="TEST_VAR")}

    with patch.dict(os.environ, {"TEST_VAR": "cascade_value"}):
        outputs = env_probe(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "cascade_value"


def test_env_probe_returns_none_if_env_missing():
    inputs = {"name": Token(payload="NON_EXISTENT_VAR")}

    # Ensure it's not in environ
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]

    outputs = env_probe(inputs, MagicMock(), MagicMock())
    assert outputs["out"].payload is None
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/probe/test_pulse.py
~~~~~
~~~~~python.old
async def test_pulse_generator_passes_token_forward():
    trace = {"origin": "pulse_test"}
    inputs = {"trigger": Token(payload="BOOM", trace=trace)}

    outputs = await pulse_generator(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "BOOM"
    assert outputs["out"].trace["origin"] == "pulse_test"
~~~~~
~~~~~python.new
def test_pulse_generator_passes_token_forward():
    trace = {"origin": "pulse_test"}
    inputs = {"trigger": Token(payload="BOOM", trace=trace)}

    outputs = pulse_generator(inputs, MagicMock(), MagicMock())

    assert outputs["out"].payload == "BOOM"
    assert outputs["out"].trace["origin"] == "pulse_test"
~~~~~

#### Acts 6: 更新 Resource Tests

~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_continuous.py
~~~~~
~~~~~python.old
async def test_continuous_allocator_grants_memory(partial_ledger):
    inputs = {
        "ledger_in": Token(payload=partial_ledger),
        "req_in": Token(payload=2.1),
    }
    outputs = await continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1
    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(2.4)


async def test_continuous_allocator_recirculates_large_request(starved_ledger):
    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = await continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token
    assert outputs["ledger_out"].payload.available == 1.0


async def test_continuous_reclaimer_replenish():
    ledger = ContinuousLedger(total=16.0, available=0.5)
    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=1.2)}
    outputs = await continuous_reclaimer(inputs, MagicMock(), MagicMock())

    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(1.7)
~~~~~
~~~~~python.new
def test_continuous_allocator_grants_memory(partial_ledger):
    inputs = {
        "ledger_in": Token(payload=partial_ledger),
        "req_in": Token(payload=2.1),
    }
    outputs = continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1
    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(2.4)


def test_continuous_allocator_recirculates_large_request(starved_ledger):
    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token
    assert outputs["ledger_out"].payload.available == 1.0


def test_continuous_reclaimer_replenish():
    ledger = ContinuousLedger(total=16.0, available=0.5)
    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=1.2)}
    outputs = continuous_reclaimer(inputs, MagicMock(), MagicMock())

    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(1.7)
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python.old
async def test_discrete_allocator_grants_when_available(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "req_in": Token(payload=2)}
    outputs = await discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
~~~~~
~~~~~python.new
def test_discrete_allocator_grants_when_available(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "req_in": Token(payload=2)}
    outputs = discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python.old
async def test_discrete_allocator_recirculates_when_starved(starved_ledger):
    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = await discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
~~~~~
~~~~~python.new
def test_discrete_allocator_recirculates_when_starved(starved_ledger):
    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python.old
async def test_discrete_reclaimer_releases_resource(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "rel_in": Token(payload=3)}
    outputs = await discrete_reclaimer(inputs, MagicMock(), MagicMock())

    updated_ledger = outputs["ledger_out"].payload
~~~~~
~~~~~python.new
def test_discrete_reclaimer_releases_resource(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "rel_in": Token(payload=3)}
    outputs = discrete_reclaimer(inputs, MagicMock(), MagicMock())

    updated_ledger = outputs["ledger_out"].payload
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python.old
async def test_sequential_rel_and_req():
    ledger = DiscreteLedger(total=10, available=2)
    mock_node = MagicMock()
    mock_resources = MagicMock()

    rel_outputs = await discrete_reclaimer(
        {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)},
        mock_node,
        mock_resources,
    )
    new_ledger = rel_outputs["ledger_out"].payload

    alloc_outputs = await discrete_allocator(
        {"ledger_in": Token(payload=new_ledger), "req_in": Token(payload=4)},
        mock_node,
        mock_resources,
    )

    assert "gnt_out" in alloc_outputs
~~~~~
~~~~~python.new
def test_sequential_rel_and_req():
    ledger = DiscreteLedger(total=10, available=2)
    mock_node = MagicMock()
    mock_resources = MagicMock()

    rel_outputs = discrete_reclaimer(
        {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)},
        mock_node,
        mock_resources,
    )
    new_ledger = rel_outputs["ledger_out"].payload

    alloc_outputs = discrete_allocator(
        {"ledger_in": Token(payload=new_ledger), "req_in": Token(payload=4)},
        mock_node,
        mock_resources,
    )

    assert "gnt_out" in alloc_outputs
~~~~~

#### Acts 7: 更新 System Tests

~~~~~act
patch_file
packages/cascade-std/tests/unit/system/test_drainer.py
~~~~~
~~~~~python.old
async def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await drain_signal(inputs, MagicMock(), MagicMock())

    assert "out" in outputs
~~~~~
~~~~~python.new
def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = drain_signal(inputs, MagicMock(), MagicMock())

    assert "out" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/system/test_terminator.py
~~~~~
~~~~~python.old
async def test_halt_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await halt_signal(inputs, MagicMock(), MagicMock())

    assert "out" in outputs
~~~~~
~~~~~python.new
def test_halt_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = halt_signal(inputs, MagicMock(), MagicMock())

    assert "out" in outputs
~~~~~

#### Acts 8: 更新 Triad Tests

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
async def test_standard_bleacher_extracts_payloads():
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_bleach_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    outputs = await standard_bleacher(inputs, node, MagicMock())

    assert "worker_input" in outputs
~~~~~
~~~~~python.new
def test_standard_bleacher_extracts_payloads():
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_bleach_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    outputs = standard_bleacher(inputs, node, MagicMock())

    assert "worker_input" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
async def test_standard_bleacher_generates_trace_with_timestamp():
    MOCK_TIMESTAMP = 12345.6789
    node = create_mock_bleach_node({"data": PortRole.DATA})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher({"data": Token(payload=1)}, node, MagicMock())

    assert "trace_output" in outputs
~~~~~
~~~~~python.new
def test_standard_bleacher_generates_trace_with_timestamp():
    MOCK_TIMESTAMP = 12345.6789
    node = create_mock_bleach_node({"data": PortRole.DATA})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({"data": Token(payload=1)}, node, MagicMock())

    assert "trace_output" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
async def test_standard_bleacher_with_empty_inputs():
    MOCK_TIMESTAMP = 100.0
    node = create_mock_bleach_node({})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher({}, node, MagicMock())

    assert "worker_input" in outputs
~~~~~
~~~~~python.new
def test_standard_bleacher_with_empty_inputs():
    MOCK_TIMESTAMP = 100.0
    node = create_mock_bleach_node({})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher({}, node, MagicMock())

    assert "worker_input" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
async def test_standard_bleacher_merges_traces():
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }
    node = create_mock_bleach_node({"token_a": PortRole.DATA, "token_b": PortRole.DATA})

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher(inputs, node, MagicMock())

    assert "trace_output" in outputs
~~~~~
~~~~~python.new
def test_standard_bleacher_merges_traces():
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }
    node = create_mock_bleach_node({"token_a": PortRole.DATA, "token_b": PortRole.DATA})

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = standard_bleacher(inputs, node, MagicMock())

    assert "trace_output" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_observer_publishes_ir_to_bus(
    mock_bus: MagicMock, mock_resources: MagicMock
):
    # 1. Prepare Input
    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {"rid": "run-1"},
        "phy": {"nid": "node-abc.stain"},
        "data": {"state": EventState.SUCCEEDED, "duration_ms": 100},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, MagicMock(), mock_resources)

    # 3. Assert
    # Assert that the observer requested the bus from resources
    mock_resources.get.assert_called_once_with("system.event_bus")

    # Assert that the observer published the IR payload to the bus
    mock_bus.publish_ir.assert_called_once_with(ir_payload)


@pytest.mark.asyncio
async def test_observer_handles_no_bus(mock_resources: MagicMock):
    # Set up resources to return None for the bus
    mock_resources.get.return_value = None

    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {},
        "phy": {"nid": "n1"},
        "data": {},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # Execute and expect no exceptions
    await standard_observer(inputs, MagicMock(), mock_resources)

    # Bus's publish method should not have been called
    # (since bus itself is None, getattr would fail if not guarded)
    # The main test is that it doesn't crash.
~~~~~
~~~~~python.new
def test_observer_publishes_ir_to_bus(
    mock_bus: MagicMock, mock_resources: MagicMock
):
    # 1. Prepare Input
    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {"rid": "run-1"},
        "phy": {"nid": "node-abc.stain"},
        "data": {"state": EventState.SUCCEEDED, "duration_ms": 100},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    standard_observer(inputs, MagicMock(), mock_resources)

    # 3. Assert
    # Assert that the observer requested the bus from resources
    mock_resources.get.assert_called_once_with("system.event_bus")

    # Assert that the observer published the IR payload to the bus
    mock_bus.publish_ir.assert_called_once_with(ir_payload)


def test_observer_handles_no_bus(mock_resources: MagicMock):
    # Set up resources to return None for the bus
    mock_resources.get.return_value = None

    ir_payload: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": 123.456,
        "ctx": {},
        "phy": {"nid": "n1"},
        "data": {},
    }
    event_token = Token(payload=ir_payload, trace={})
    inputs = {"event_token": event_token}

    # Execute and expect no exceptions
    standard_observer(inputs, MagicMock(), mock_resources)

    # Bus's publish method should not have been called
    # (since bus itself is None, getattr would fail if not guarded)
    # The main test is that it doesn't crash.
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
~~~~~
~~~~~python.new
def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
~~~~~
~~~~~python.new
def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
~~~~~
~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    output_token = outputs["output_default"]
~~~~~
~~~~~python.new
def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_stainer(inputs, node, MagicMock())

    output_token = outputs["output_default"]
~~~~~

### 下一步建议

在应用此计划并确认 `cascade-std` 的测试套件完全通过后，我们应该继续在更高层次的集成测试中验证这些同步 IC 的行为，确保它们在 `Reactor` 的同步执行模型下能正确协作。
