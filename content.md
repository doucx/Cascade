简要回答
好的，分析完毕。我的 `sed` 策略过于简单，未能处理多行函数调用，并且完全漏掉了 `test_observer.py` 的调用点修复。感谢您的指正。

我们现在将一次性修复剩余的故障并根据您的建议重构这些测试文件以消除重复代码（DRY）。

## [WIP] fix(tests): 修复并重构 cascade-std 单元测试以提高代码质量

### 错误分析
1.  `test_discrete.py`: `sed` 命令未能匹配多行函数调用，导致 `test_sequential_rel_and_req` 失败。
2.  `test_observer.py`: 在上一个计划中，我仅添加了 `MagicMock` 的导入，但忘记了更新其三个测试用例中的函数调用点。
3.  **代码质量**: `test_discrete.py`, `test_continuous.py`, 和 `test_observer.py` 包含大量重复的设置代码，违反了 DRY 原则。

### 用户需求
1.  修复所有剩余的测试失败。
2.  重构相关测试文件以提高代码质量和可维护性。

### 评论
这是一个典型的“修复并改进”循环。简单的批量替换不足以应对代码的多样性。现在，我们将采用更精确的 `write_file` 操作，这不仅能保证修复的正确性，还能通过引入 `pytest` 的 Fixture 范式来提升测试代码的整体质量，使其更简洁、更易于理解。

### 目标
1.  修复 `test_discrete.py` 中的多行调用失败。
2.  修复 `test_observer.py` 中的所有调用失败。
3.  重构 `test_discrete.py`、`test_continuous.py` 和 `test_observer.py` 以使用 Fixture，消除代码重复。

### 基本原理
我们将使用 `pytest.fixture` 来封装重复的对象创建逻辑（如 `Ledger`、`Queue`）。测试函数将通过参数声明其依赖，由 `pytest` 自动注入。这将使每个测试的主体部分只关注其独特的逻辑和断言，从而使代码更清晰、更符合 TDD 的最佳实践。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/std #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `test_discrete.py`

我们使用 `write_file` 彻底重写此文件。这将同时修复失败的测试并消除重复代码。

~~~~~act
write_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import (
    discrete_allocator,
    discrete_reclaimer,
    DiscreteLedger,
)


@pytest.fixture
def available_ledger() -> DiscreteLedger:
    """A ledger with total 10, available 5."""
    return DiscreteLedger(total=10, available=5)


@pytest.fixture
def starved_ledger() -> DiscreteLedger:
    """A ledger with total 10, available 1."""
    return DiscreteLedger(total=10, available=1)


async def test_discrete_allocator_grants_when_available(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "req_in": Token(payload=2)}
    outputs = await discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs


async def test_discrete_allocator_recirculates_when_starved(starved_ledger):
    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = await discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1


async def test_discrete_reclaimer_releases_resource(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "rel_in": Token(payload=3)}
    outputs = await discrete_reclaimer(inputs, MagicMock(), MagicMock())

    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8


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
    assert alloc_outputs["ledger_out"].payload.available == 1
~~~~~

#### Acts 2: 重构 `test_continuous.py`

同理，我们重写此文件以提高代码质量。

~~~~~act
write_file
packages/cascade-std/tests/unit/resource/test_continuous.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import (
    continuous_allocator,
    continuous_reclaimer,
    ContinuousLedger,
)


@pytest.fixture
def partial_ledger() -> ContinuousLedger:
    """Ledger with 16.0 total, 4.5 available."""
    return ContinuousLedger(total=16.0, available=4.5)


@pytest.fixture
def starved_ledger() -> ContinuousLedger:
    """Ledger with 16.0 total, 1.0 available."""
    return ContinuousLedger(total=16.0, available=1.0)


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

#### Acts 3: 修复并重构 `test_observer.py`

最后，我们重写 observer 测试，修复调用签名并引入 fixture。

~~~~~act
write_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python
import pytest
from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


@pytest.fixture
def event_queue() -> Queue:
    return Queue()


async def test_observer_processes_start_event(event_queue: Queue):
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event(event_queue: Queue):
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace(event_queue: Queue):
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), MagicMock(), queue=event_queue)

    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
~~~~~

### 下一步建议
所有已知的测试故障都已修复，并且相关的测试文件也已重构。现在是再次运行测试套件以确认系统已达到稳定（全绿）状态的最佳时机。确认后，我们将正式完成阶段 1 并准备进入阶段 2。
