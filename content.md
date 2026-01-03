好的，我们即刻将代码审查的结论转化为一个可执行的 Quipu 计划。

这个计划将全面地、原子化地将 `cascade-std` 库中的所有 IC 函数转换为原生异步 `async def`，并同步更新所有相关的单元测试以确保功能的正确性。

## [WIP] refactor(std): 将所有 IC 函数转换为原生异步

### 用户需求
根据代码审查的结论，将 `cascade-std` 包中的所有同步 IC 函数转换为其原生异步 (`async def`) 的对应版本，以提升性能并与 VM 的异步执行模型对齐。

### 评论
这是一个至关重要的性能优化。当前 `cascade-std` 中的所有 IC 函数都是轻量级、非阻塞的纯计算，将它们放入线程池中执行会带来不必要的上下文切换开销。将它们转换为 `async def`，可以使其在 `asyncio` 事件循环上以接近零成本的方式运行，从而充分释放 Cascade 3.0 异步 VM 的性能潜力。

### 目标
1.  将 `cascade-std` 的 `triad`, `probe`, `system`, `resource` 模块中的所有 IC 函数签名从 `def` 修改为 `async def`。
2.  特别适配 `standard_observer`，使其能够处理 `asyncio.Queue` 并使用 `await queue.put()`。
3.  更新所有相关的单元测试，在调用这些现在是异步的 IC 函数时使用 `await`，并确保所有测试通过。

### 基本原理
通过批量应用 `patch_file` 来修改 IC 的函数签名。对于 `observer` 的修改，由于涉及导入和方法调用方式的改变，需要一个更精确的补丁。对于测试文件，由于每个测试函数都需要从 `def` 变为 `async def` 并添加 `await`，使用 `write_file` 提供完整的新文件内容是更清晰、更不容易出错的做法。

### 标签
#intent/refine #flow/ready #priority/high
#scope/core #scope/dx #comp/tests
#ai/instruct
#task/domain/core-logic #task/object/std-library #task/action/async-refactor
#task/state/begin

---

### Script

#### Acts 1: 异步化 `triad` 模块的 IC

我们将首先转换核心的 `bleacher`, `stainer`, 和 `observer`。`observer` 的转换会特别处理 `asyncio.Queue`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
def standard_bleacher(inputs: Dict[str, Token], node: BleachNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def standard_bleacher(inputs: Dict[str, Token], node: BleachNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
def standard_stainer(inputs: Dict[str, Token], node: StainNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def standard_stainer(inputs: Dict[str, Token], node: StainNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from queue import Queue

from cascade.spec.physics import Token


@dataclass
class ObservedEvent:
    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    queue.put(event)
~~~~~
~~~~~python.new
from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from asyncio import Queue

from cascade.spec.physics import Token


@dataclass
class ObservedEvent:
    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


async def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)
~~~~~

#### Acts 2: 异步化 `probe` 模块的 IC

转换 `context`, `env`, 和 `pulse` 采样器。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/context.py
~~~~~
~~~~~python.old
def param_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def param_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/env.py
~~~~~
~~~~~python.old
def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/pulse.py
~~~~~
~~~~~python.old
def pulse_generator(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def pulse_generator(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~

#### Acts 3: 异步化 `system` 模块的 IC

转换 `drainer` 和 `terminator` 系统信号发射器。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
def halt_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def halt_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~

#### Acts 4: 异步化 `resource` 模块的 IC

转换 `continuous` 和 `discrete` 资源经纪人。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
def continuous_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def continuous_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
def discrete_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~
~~~~~python.new
async def discrete_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
~~~~~

#### Acts 5: 更新单元测试以适应异步 IC

现在，我们将重写所有相关的单元测试，使其变为异步并使用 `await` 调用被测函数。

~~~~~act
write_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python
from unittest.mock import patch, MagicMock

from cascade.spec.physics import Token
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.triad import BleachNode
from cascade.std.triad.bleacher import standard_bleacher


def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node


async def test_standard_bleacher_extracts_payloads():
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_bleach_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    outputs = await standard_bleacher(inputs, node)

    assert "worker_input" in outputs
    worker_token = outputs["worker_input"]
    assert isinstance(worker_token, Token)
    assert worker_token.payload == {"arg1": "hello", "arg2": 123}


async def test_standard_bleacher_generates_trace_with_timestamp():
    MOCK_TIMESTAMP = 12345.6789
    node = create_mock_bleach_node({"data": PortRole.DATA})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher({"data": Token(payload=1)}, node)

    assert "trace_output" in outputs
    trace_token = outputs["trace_output"]
    assert isinstance(trace_token, Token)
    assert isinstance(trace_token.payload, dict)
    assert trace_token.payload.get("start_ts") == MOCK_TIMESTAMP


async def test_standard_bleacher_with_empty_inputs():
    MOCK_TIMESTAMP = 100.0
    node = create_mock_bleach_node({})

    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher({}, node)

    assert "worker_input" in outputs
    assert outputs["worker_input"].payload == {}

    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {"start_ts": MOCK_TIMESTAMP}


async def test_standard_bleacher_merges_traces():
    inputs = {
        "token_a": Token(payload=1, trace={"id": "A", "source": "X"}),
        "token_b": Token(payload=2, trace={"id": "B", "retry": 1}),
    }
    node = create_mock_bleach_node({"token_a": PortRole.DATA, "token_b": PortRole.DATA})

    MOCK_TIMESTAMP = 200.0
    with patch("time.monotonic", return_value=MOCK_TIMESTAMP):
        outputs = await standard_bleacher(inputs, node)

    assert "trace_output" in outputs
    trace_payload = outputs["trace_output"].payload

    # Check for merged data
    assert trace_payload.get("id") == "B"  # Last write wins on conflict
    assert trace_payload.get("source") == "X"
    assert trace_payload.get("retry") == 1

    # Check for new timestamp
    assert trace_payload.get("start_ts") == MOCK_TIMESTAMP
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python
import pytest
from unittest.mock import patch, MagicMock

from cascade.spec.physics import Token
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.triad import StainNode
from cascade.std.triad.stainer import standard_stainer


def create_mock_stain_node(output_ports_config):
    node = MagicMock(spec=StainNode)
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


async def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    assert output_token.tag == "default"
    assert output_token.trace["id"] == "task_A"
    assert output_token.trace["start_ts"] == start_ts
    assert output_token.trace["end_ts"] == end_ts
    assert output_token.trace["duration"] == 2.5


async def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node)

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    assert output_token.tag == "error"
    assert output_token.trace["end_ts"] == end_ts
    assert pytest.approx(output_token.trace["duration"]) == 0.1


async def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node)

    output_token = outputs["output"]
    assert output_token.trace["duration"] == 0.0
    assert output_token.trace["end_ts"] == end_ts
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python
from asyncio import Queue

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


async def test_observer_processes_start_event():
    # 1. Setup
    queue = Queue()
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event():
    # 1. Setup
    queue = Queue()
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace():
    # 1. Setup
    queue = Queue()
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    # 2. Execute
    await standard_observer(inputs, queue)

    # 3. Assert
    assert queue.qsize() == 1
    observed = await queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_context.py
~~~~~
~~~~~python
from unittest.mock import MagicMock, patch
from cascade.spec.physics import Token
from cascade.std.probe.context import param_probe


async def test_param_probe_lookups_value():
    inputs = {"name": Token(payload="db_url"), "trigger": Token(payload=None)}

    # Mock WorkflowContext
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = "sqlite:///:memory:"

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock())

    assert outputs["out"].payload == "sqlite:///:memory:"
    mock_ctx.get_value.assert_called_once_with("db_url")


async def test_param_probe_returns_none_if_missing():
    inputs = {"name": Token(payload="missing"), "trigger": Token(payload=None)}
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = None

    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = await param_probe(inputs, MagicMock())

    assert outputs["out"].payload is None
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_env.py
~~~~~
~~~~~python
import os
from unittest.mock import MagicMock, patch
from cascade.spec.physics import Token
from cascade.std.probe.env import env_probe


async def test_env_probe_samples_os_environ():
    inputs = {"name": Token(payload="TEST_VAR")}

    with patch.dict(os.environ, {"TEST_VAR": "cascade_value"}):
        outputs = await env_probe(inputs, MagicMock())

    assert outputs["out"].payload == "cascade_value"


async def test_env_probe_returns_none_if_env_missing():
    inputs = {"name": Token(payload="NON_EXISTENT_VAR")}

    # Ensure it's not in environ
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]

    outputs = await env_probe(inputs, MagicMock())
    assert outputs["out"].payload is None
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_pulse.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.probe.pulse import pulse_generator


async def test_pulse_generator_passes_token_forward():
    trace = {"origin": "pulse_test"}
    inputs = {"trigger": Token(payload="BOOM", trace=trace)}

    outputs = await pulse_generator(inputs, MagicMock())

    assert outputs["out"].payload == "BOOM"
    assert outputs["out"].trace["origin"] == "pulse_test"
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/system/test_drainer.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.drainer import drain_signal


async def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await drain_signal(inputs, MagicMock())

    assert "out" in outputs
    output_payload = outputs["out"].payload

    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "DRAIN"
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/system/test_terminator.py
~~~~~
~~~~~python
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.terminator import halt_signal


async def test_halt_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}

    outputs = await halt_signal(inputs, MagicMock())

    assert "out" in outputs
    output_payload = outputs["out"].payload

    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "HALT"
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/resource/test_continuous.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import continuous_broker, ContinuousLedger

async def test_continuous_broker_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1) # Request 2.1GB
    }
    
    outputs = await continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1
    
    updated = outputs["ledger_out"].payload
    # 4.5 - 2.1 = 2.4
    assert updated.available == pytest.approx(2.4)

async def test_continuous_broker_recirculates_large_request():
    # Ledger: Available 1.0GB
    ledger = ContinuousLedger(total=16.0, available=1.0)
    
    req_token = Token(payload=1.1)
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": req_token
    }
    
    outputs = await continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token
    
    assert outputs["ledger_out"].payload.available == 1.0

async def test_continuous_broker_replenish_and_grant():
    # Ledger: Available 0.5. Request 1.5. Release 1.2.
    # Logic: 0.5 + 1.2 = 1.7. 1.7 >= 1.5. Grant.
    ledger = ContinuousLedger(total=16.0, available=0.5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=1.5),
        "rel_in": Token(payload=1.2)
    }
    
    outputs = await continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" in outputs
    updated = outputs["ledger_out"].payload
    # 0.5 + 1.2 - 1.5 = 0.2
    assert updated.available == pytest.approx(0.2)
~~~~~
~~~~~act
write_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import discrete_broker, DiscreteLedger

async def test_discrete_broker_grants_when_available():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Grant
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2
    
    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs

async def test_discrete_broker_recirculates_when_starved():
    # Ledger: Total 10, Available 1
    ledger = DiscreteLedger(total=10, available=1)
    
    req_token = Token(payload=5)
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": req_token
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check No Grant
    assert "gnt_out" not in outputs
    
    # Check Recirculation
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token # Identity check
    
    # Check Ledger Unchanged
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1

async def test_discrete_broker_releases_resource():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "rel_in": Token(payload=3)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8

async def test_discrete_broker_simultaneous_rel_and_req():
    # Ledger: Available 2. Request 4. Release 3.
    # Logic: Release happens first, so Available becomes 2+3=5. Then Request 4 succeeds.
    ledger = DiscreteLedger(total=10, available=2)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=4),
        "rel_in": Token(payload=3)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Grant
    assert "gnt_out" in outputs
    
    # Check Ledger: 2 + 3 - 4 = 1
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1
~~~~~

### 下一步建议
我们已经成功将 `cascade-std` 库全面异步化。

下一步关键行动是**修改 `cascade-vm` 的 `PhysicsExecutor`**。当前它使用 `ThreadPoolExecutor` 来运行所有函数，这是为同步阻塞函数设计的。我们需要实现一个新的“智能分发”策略：

1.  **检查函数类型**：在 `_fire` 方法中，检查 `function_map` 中得到的函数是否是协程函数 (`inspect.iscoroutinefunction`)。
2.  **直接 `await`**：如果是协程函数，就直接 `await func(...)`。
3.  **提交到线程池**：如果仍然是同步函数（为了向后兼容或处理CPU密集型任务），才使用当前的 `executor.submit(...)` 逻辑。

这将确保我们能真正享受到本次重构带来的性能优势。如果你同意，我将为你生成实现该逻辑的计划。
