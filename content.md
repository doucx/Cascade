## 好的，我们继续完成剩余的任务。

##### C. Continuous Resource ICs

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode


@dataclass
class ContinuousLedger:
    total: float
    available: float


def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = float(req_token.payload)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        ledger.available -= req_amount
        # Sovereignty: In the future, we should use trace-based routing here like discrete.py
        # For now, just remove the tag to fix the crash.
        outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    release_amount = float(inputs["rel_in"].payload)
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}
~~~~~
~~~~~python.new
from typing import Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ContinuousAllocatorSpec, ContinuousReclaimerSpec
from cascade.std.kernel_tools import implements


@dataclass
class ContinuousLedger:
    total: float
    available: float


@implements(ContinuousAllocatorSpec)
def continuous_allocator(
    io: ContinuousAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    req_token = io.req_in

    assert ledger_token is not None, "Ledger token for allocator is missing"
    assert req_token is not None, "Request token for allocator is missing"

    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_amount = float(req_token.payload)

    if ledger.available >= req_amount:
        ledger.available -= req_amount
        # Sovereignty: In the future, we should use trace-based routing here like discrete.py
        # For now, just remove the tag to fix the crash.
        io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        io.req_out = req_token

    io.ledger_out = Token(payload=ledger)


@implements(ContinuousReclaimerSpec)
def continuous_reclaimer(
    io: ContinuousReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    rel_token = io.rel_in

    assert ledger_token is not None, "Ledger token for reclaimer is missing"
    assert rel_token is not None, "Release token for reclaimer is missing"

    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    release_amount = float(rel_token.payload)
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)
~~~~~

### 下一步建议

至此，我们已经成功地将所有清单中的 IC 迁移到了新的 PIDL 模式。`cascade-std` 库的物理接口层现在已经完全标准化和类型化。

下一步的关键是验证这些改动的正确性。我建议：

1.  **运行静态分析**: 在整个项目上运行 `pyright` 或 `mypy`，确保没有引入任何新的类型错误。
2.  **执行单元测试**: 运行 `cascade-std` 包内的所有单元测试。由于我们仅仅是重构了接口层而没有改变核心逻辑，现有的测试应该仍然能够通过。如果测试失败，说明接口适配器 (`@implements` 装饰器) 可能存在问题，需要进行调试。
3.  **创建 Git 提交**: 一旦所有检查通过，你可以将这些变更作为一个原子提交。一个合适的提交信息是：`refactor(std): Migrate all remaining ICs to typed PhysicsSpec interfaces`。
