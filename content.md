好的，我们继续 T4 的核心任务：实现 `ContinuousBroker`。

基于 `DiscreteBroker` 的成功预研，我们将直接复用“自环账本 + 拓扑回流”的模式。区别主要在于数据类型（float vs int）和应用场景（连续量，如内存/存储）。

## [WIP] feat: 实现连续资源经纪人 (ContinuousBroker)

### 用户需求

根据 `Act 0.5` 路线图，执行任务 T4 的剩余部分：在 `cascade-std` 中实现 `ContinuousBroker`。

### 评论

`ContinuousBroker` 是 Cascade 3.0 处理复杂物理资源限制（如 `memory=5.1GB`）的关键组件。它证明了我们的物理场模型不仅能处理计数信号，还能处理模拟信号。

### 目标

1.  在 `cascade-std/resource` 中创建 `continuous.py`。
2.  实现 `ContinuousLedger` 数据类和 `continuous_broker` 函数。
3.  编写单元测试，验证浮点数资源管理的正确性和回流机制。

### 基本原理

逻辑与 `DiscreteBroker` 几乎完全一致，主要差异在于 `Ledger` 的字段类型。我们将保持接口的统一性。
*   **精度处理**：虽然 Python 的 `float` 是双精度的，但在极端情况下可能会有微小误差。对于本阶段的实现，我们暂不引入 `Decimal`，直接使用 `float`，这足以覆盖绝大多数工程需求（如 GB 级别的内存管理）。

### 标签

#intent/build #flow/ready #priority/high #comp/std #scope/core #ai/instruct #task/domain/architecture #task/object/continuous-broker #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 实现 `ContinuousBroker`

~~~~~act
write_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python
from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physics import Token, PhysicsNode

@dataclass
class ContinuousLedger:
    total: float
    available: float

def continuous_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    A Continuous Resource Broker using the Self-Loop Ledger pattern.
    Handles floating-point resources (e.g., memory, disk space).
    
    Inputs:
        ledger_in: Token containing ContinuousLedger
        req_in: (Optional) Token requesting N units. Payload: float
        rel_in: (Optional) Token releasing N units. Payload: float
        
    Outputs:
        ledger_out: Updated ledger
        gnt_out: (Conditional) Grant token
        req_out: (Conditional) Recirculated request token
    """
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data
    
    outputs: Dict[str, Token] = {}
    
    # 1. Process Release
    if "rel_in" in inputs:
        release_amount = float(inputs["rel_in"].payload)
        # Simple clamp to avoid floating point drift exceeding total
        ledger.available = min(ledger.total, ledger.available + release_amount)
    
    # 2. Process Request
    if "req_in" in inputs:
        req_token = inputs["req_in"]
        req_amount = float(req_token.payload)
        
        # Use a small epsilon for float comparison if needed, but >= usually suffices
        if ledger.available >= req_amount:
            ledger.available -= req_amount
            outputs["gnt_out"] = Token(payload=req_amount)
        else:
            # Recirculate
            outputs["req_out"] = req_token
            
    # 3. Emit Updated Ledger
    outputs["ledger_out"] = Token(payload=ledger)
    
    return outputs
~~~~~

#### Acts 2: 编写单元测试

测试逻辑与离散版类似，但我们使用浮点数来验证。

~~~~~act
write_file
packages/cascade-std/tests/unit/resource/test_continuous.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import continuous_broker, ContinuousLedger

def test_continuous_broker_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1) # Request 2.1GB
    }
    
    outputs = continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1
    
    updated = outputs["ledger_out"].payload
    # 4.5 - 2.1 = 2.4
    assert updated.available == pytest.approx(2.4)

def test_continuous_broker_recirculates_large_request():
    # Ledger: Available 1.0GB
    ledger = ContinuousLedger(total=16.0, available=1.0)
    
    req_token = Token(payload=1.1)
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": req_token
    }
    
    outputs = continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token
    
    assert outputs["ledger_out"].payload.available == 1.0

def test_continuous_broker_replenish_and_grant():
    # Ledger: Available 0.5. Request 1.5. Release 1.2.
    # Logic: 0.5 + 1.2 = 1.7. 1.7 >= 1.5. Grant.
    ledger = ContinuousLedger(total=16.0, available=0.5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=1.5),
        "rel_in": Token(payload=1.2)
    }
    
    outputs = continuous_broker(inputs, MagicMock())
    
    assert "gnt_out" in outputs
    updated = outputs["ledger_out"].payload
    # 0.5 + 1.2 - 1.5 = 0.2
    assert updated.available == pytest.approx(0.2)
~~~~~

### 下一步建议

我们已经完成了所有计划中的功能开发任务！

Act 0.5 的所有核心目标（T1-T5）均已达成：
*   **Std 包建立**：`cascade-std` 已就位。
*   **指令迁移**：`Triad` 逻辑已迁入。
*   **采样芯片**：`Probe` 逻辑已实现。
*   **系统芯片**：`System` 逻辑已实现。
*   **资源经纪人**：`Broker` 逻辑（离散+连续）已实现。

现在，我们可以生成一个 `[COMMIT]` 计划，将资源经纪人相关的代码提交。然后，我们可以进行一次全面的回顾，或者讨论 Act 0.6 的规划。
