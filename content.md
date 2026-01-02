好的，这是一个明智的决定。任务 T4 确实是整个 Act 0.5 中最复杂的部分，我们可以先完成其他外围任务，最后再集中精力攻克它。

我们现在开始执行 **任务 T5: 实现系统主权芯片**。

这个计划将创建 `terminator` 和 `drainer` 这两个核心的系统控制芯片。它们是计算图实现“自我主权”的物理基础，允许图本身向运行时（VM）发出 `HALT` (停机) 和 `DRAIN` (耗尽) 的信号。

## [WIP] feat: 实现系统主权芯片 (System ICs)

### 用户需求

根据 `Act 0.5` 路线图，执行任务 T5：在 `cascade-std` 中实现 `terminator` 和 `drainer` 系统控制芯片，并为它们创建单元测试。

### 评论

这是 Cascade 3.0 "图的主权" 哲学的直接体现。通过将 `HALT` 和 `DRAIN` 等生命周期控制信号物化为图内部节点产生的特殊 Token，我们将控制权从外部的“上帝”调度器交还给了计算图本身。这使得图能够自洽地决定其生命周期的终结，是迈向真正自主演化物理场的关键一步。

### 目标

1.  在 `cascade-std` 中创建 `system` 目录结构。
2.  在 `cascade-spec` 中定义一个新的 `SystemControlToken` 类型，作为系统信号的标准化载体。
3.  实现 `terminator.py`，它能生成一个 `SystemControlToken(command='HALT')`。
4.  实现 `drainer.py`，它能生成一个 `SystemControlToken(command='DRAIN')`。
5.  为这两个芯片编写单元测试，验证它们能正确生成预期的控制信号。

### 基本原理

我们将首先在 `cascade-spec` 中定义 `SystemControlToken`，因为它是一个跨越 VM 和标准库边界的核心数据结构。然后，在 `cascade-std` 中实现的两个芯片函数将非常简单：它们接收任意输入 Token 作为触发器，然后构造并返回一个特定命令的 `SystemControlToken`。测试将断言返回的 Token 类型和 `command` 字段是否正确。

### 标签

#intent/build #flow/ready #priority/high #comp/std #comp/spec #scope/api #ai/instruct #task/domain/architecture #task/object/system-ics #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `system` 目录结构

我们在 `cascade-std` 中为系统控制芯片建立存放目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/src/cascade/std/system
mkdir -p packages/cascade-std/tests/unit/system
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/__init__.py
~~~~~
~~~~~python
# System Control ICs for graph lifecycle management (Sovereignty).
~~~~~

#### Acts 2: 在 `cascade-spec` 中定义 `SystemControlToken`

为了让 VM 能够识别这些特殊信号，我们首先在规范包中定义 `SystemControlToken`。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/system.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SystemControlToken:
    """
    A special token that signals a lifecycle control command to the VM/Reactor.
    It is NOT a data token and should be handled by a special system bus.
    """
    command: str
    payload: Any = None
~~~~~

#### Acts 3: 实现系统主权芯片 (ICs)

现在，我们实现 `terminator` 和 `drainer`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken

def halt_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Receives a trigger token and emits a SIG_HALT system control token.
    This requests an immediate, hard shutdown of the Reactor.
    """
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command="HALT")
    return {"out": Token(payload=control_token)}
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken

def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Receives a trigger and emits a SIG_DRAIN system control token.
    This signals that a branch of the graph will produce no new data,
    aiding in graceful shutdown detection.
    """
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}
~~~~~

#### Acts 4: 创建单元测试

最后，为这两个芯片编写单元测试。

~~~~~act
write_file
packages/cascade-std/tests/unit/system/test_terminator.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.terminator import halt_signal

def test_halt_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}
    
    outputs = halt_signal(inputs, MagicMock())
    
    assert "out" in outputs
    output_payload = outputs["out"].payload
    
    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "HALT"
~~~~~

~~~~~act
write_file
packages/cascade-std/tests/unit/system/test_drainer.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.spec.system import SystemControlToken
from cascade.std.system.drainer import drain_signal

def test_drain_signal_produces_correct_token():
    inputs = {"trigger": Token(payload=None)}
    
    outputs = drain_signal(inputs, MagicMock())
    
    assert "out" in outputs
    output_payload = outputs["out"].payload
    
    assert isinstance(output_payload, SystemControlToken)
    assert output_payload.command == "DRAIN"
~~~~~

### 下一步建议

我们已经成功地实现了系统主权芯片，完成了 `Act 0.5` 路线图中的大部分任务（T1, T2, T3, T5）。

现在只剩下最后一个，也是最具挑战性的任务：**T4: 实现资源经纪人芯片 (Resource Broker ICs)**。这个任务对于实现物理层面的资源管理和背压至关重要。

我建议我们现在开始着手这项任务。如果你准备好了，我将开始创建 `resource` 目录并实现 `DiscreteBroker`。
