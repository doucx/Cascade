你的分析很及时。这是典型的重构副作用：当我们拆分并重命名了核心函数时，旧的单元测试因为引用了不存在的名称而导致加载失败。

我将更新 `cascade-std` 的单元测试，使其适配新的 `allocator` / `reclaimer` 模式。

## [WIP] test(std): 更新资源 IC 单元测试以适配 Allocator/Reclaimer 拆分

### 错误分析

在之前的步骤中，我们将 `discrete_broker` 和 `continuous_broker` 拆分为了独立的 `allocator`（处理申请）和 `reclaimer`（处理释放）函数。
由于 `cascade-std` 目录下的单元测试仍然试图从这些模块中导入已不存在的 `broker` 函数，导致 `pytest` 在收集测试用例阶段抛出 `ImportError`。

### 用户需求
更新 `cascade-std` 的单元测试，使其能够正确导入并验证拆分后的资源协商 IC 组件。

### 评论
单元测试的更新不仅是为了通过 CI，更是为了验证拆分后的逻辑是否依然符合物理预期。拆分后的 Allocator 和 Reclaimer 职责更加明确，测试也应相应地分为“申请逻辑”和“回收逻辑”两个维度。

### 目标
1.  修改 `test_continuous.py`：更新导入，拆分测试用例。
2.  修改 `test_discrete.py`：更新导入，拆分测试用例。
3.  确保所有测试逻辑反映了新的函数签名（输入和输出端口名保持不变，但职责已分离）。

### 基本原理
由于物理端口名（`ledger_in`, `req_in`, `gnt_out` 等）在拆分时被保留了，大部分测试逻辑只需调整导入和函数名即可工作。对于原本测试“同时进行申请和释放”的用例，现在应改为顺序调用 Allocator 和 Reclaimer，以模拟它们在物理场中对 Ledger 的竞争。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/unit-test #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 更新 Continuous Broker 单元测试

~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_continuous.py
~~~~~
~~~~~python.old
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import continuous_broker, ContinuousLedger


async def test_continuous_broker_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1),  # Request 2.1GB
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
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

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
        "rel_in": Token(payload=1.2),
    }

    outputs = await continuous_broker(inputs, MagicMock())

    assert "gnt_out" in outputs
    updated = outputs["ledger_out"].payload
    # 0.5 + 1.2 - 1.5 = 0.2
    assert updated.available == pytest.approx(0.2)
~~~~~
~~~~~python.new
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import (
    continuous_allocator,
    continuous_reclaimer,
    ContinuousLedger,
)


async def test_continuous_allocator_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1),  # Request 2.1GB
    }

    outputs = await continuous_allocator(inputs, MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1

    updated = outputs["ledger_out"].payload
    # 4.5 - 2.1 = 2.4
    assert updated.available == pytest.approx(2.4)


async def test_continuous_allocator_recirculates_large_request():
    # Ledger: Available 1.0GB
    ledger = ContinuousLedger(total=16.0, available=1.0)

    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await continuous_allocator(inputs, MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token

    assert outputs["ledger_out"].payload.available == 1.0


async def test_continuous_reclaimer_replenish():
    # Ledger: Available 0.5. Release 1.2.
    ledger = ContinuousLedger(total=16.0, available=0.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "rel_in": Token(payload=1.2),
    }

    outputs = await continuous_reclaimer(inputs, MagicMock())

    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(1.7)
~~~~~

#### Acts 2: 更新 Discrete Broker 单元测试

~~~~~act
patch_file
packages/cascade-std/tests/unit/resource/test_discrete.py
~~~~~
~~~~~python.old
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import discrete_broker, DiscreteLedger


async def test_discrete_broker_grants_when_available():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "req_in": Token(payload=2)}

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
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await discrete_broker(inputs, MagicMock())

    # Check No Grant
    assert "gnt_out" not in outputs

    # Check Recirculation
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token  # Identity check

    # Check Ledger Unchanged
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1


async def test_discrete_broker_releases_resource():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)}

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
        "rel_in": Token(payload=3),
    }

    outputs = await discrete_broker(inputs, MagicMock())

    # Check Grant
    assert "gnt_out" in outputs

    # Check Ledger: 2 + 3 - 4 = 1
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1
~~~~~
~~~~~python.new
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import (
    discrete_allocator,
    discrete_reclaimer,
    DiscreteLedger,
)


async def test_discrete_allocator_grants_when_available():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "req_in": Token(payload=2)}

    outputs = await discrete_allocator(inputs, MagicMock())

    # Check Grant
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2

    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs


async def test_discrete_allocator_recirculates_when_starved():
    # Ledger: Total 10, Available 1
    ledger = DiscreteLedger(total=10, available=1)

    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await discrete_allocator(inputs, MagicMock())

    # Check No Grant
    assert "gnt_out" not in outputs

    # Check Recirculation
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token  # Identity check

    # Check Ledger Unchanged
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1


async def test_discrete_reclaimer_releases_resource():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)}

    outputs = await discrete_reclaimer(inputs, MagicMock())

    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8


async def test_sequential_rel_and_req():
    # 模拟物理场中的顺序执行
    ledger = DiscreteLedger(total=10, available=2)
    mock_node = MagicMock()

    # 1. Reclaimer fires first
    rel_outputs = await discrete_reclaimer(
        {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)}, mock_node
    )
    new_ledger = rel_outputs["ledger_out"].payload

    # 2. Allocator fires second using the new ledger
    alloc_outputs = await discrete_allocator(
        {"ledger_in": Token(payload=new_ledger), "req_in": Token(payload=4)}, mock_node
    )

    # Check Grant
    assert "gnt_out" in alloc_outputs
    assert alloc_outputs["ledger_out"].payload.available == 1
~~~~~

### 下一步建议
现在单元测试应该可以正常加载并运行了。
请重新运行所有测试（包括单元测试和集成测试），验证 Broker 的逻辑拆分是否不仅解决了死锁，而且保持了原有的功能正确性。
