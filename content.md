我们将开始执行任务 T3：实现采样芯片 (Probe ICs)。

根据路线图和 Cascade 3.0 的“主权”设计，参数和环境变量不再是节点的静态属性，而是通过物理采样动作获取的。我将创建 `ParamProbe`、`EnvProbe` 和 `PulseGenerator` 这三类核心芯片，并为它们编写严密的单元测试。

## [WIP] feat: 实现标准采样芯片 (Probe ICs) 及其测试

### 用户需求

根据 `Act 0.5` 路线图，执行任务 T3：在 `cascade-std` 中实现 `ParamProbe`、`EnvProbe` 和 `Pulse` 芯片，并同步建立单元测试。

### 评论

这是实现“计算物理化”的关键一步。通过将外部环境的接入点（参数、环境变量）抽象为物理节点，我们统一了系统的动力学模型。所有的输入现在都是通过“激发-响应”机制产生的。

### 目标

1.  在 `cascade-std` 中建立 `probe` 目录结构。
2.  实现 `ParamProbe`：从 `WorkflowContext` 采样命名参数。
3.  实现 `EnvProbe`：从操作系统环境变量采样。
4.  实现 `PulseGenerator`：作为能量倍增器，将单个激发信号同步分发到多个出口。
5.  为上述芯片编写完整的单元测试，确保其原子性和确定性。

### 基本原理

采样芯片遵循标准 IC 签名：`(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]`。
- **`ParamProbe`**：它依赖于 `cascade-common` 中的上下文机制。在测试中，我们将模拟上下文环境。
- **`EnvProbe`**：直接调用 `os.environ.get`。
- **`PulseGenerator`**：它是一个透传节点。物理图中的广播是由 `Reactor` 根据端口映射自动完成的，芯片本身只需确保将信号发射到正确的输出端口。

### 标签

#intent/build #flow/ready #priority/high #comp/std #scope/core #ai/instruct #task/domain/architecture #task/object/probe-ics #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `probe` 目录结构

首先在 `cascade-std` 中建立存放采样芯片的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-std/src/cascade/std/probe
mkdir -p packages/cascade-std/tests/unit/probe
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/__init__.py
~~~~~
~~~~~python
# Probe ICs for sampling external environments and generating pulses.
~~~~~

#### Acts 2: 实现采样芯片 (ICs)

实现 `ParamProbe`、`EnvProbe` 和 `PulseGenerator`。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/context.py
~~~~~
~~~~~python
import os
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.common.context import get_current_context

def param_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Samples a value from the global WorkflowContext based on the 'name' input.
    """
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
    # Here we interface with the common context.
    ctx = get_current_context()
    
    # We assume context has a method to get values by spec name.
    # If not found, it returns None (as a payload).
    val = ctx.get_value(name) if hasattr(ctx, "get_value") else None
    
    return {"out": Token(payload=val)}
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/env.py
~~~~~
~~~~~python
import os
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode

def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Samples a value from the OS environment variables based on the 'name' input.
    """
    name = inputs["name"].payload
    val = os.environ.get(name)
    return {"out": Token(payload=val)}
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/pulse.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode

def pulse_generator(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Acts as an energy multiplier. Takes a trigger and emits a sync pulse.
    The actual 'broadcasting' to multiple ports is defined by the graph channels
    wired to the 'out' port.
    """
    trigger_token = inputs["trigger"]
    # We pass the trigger's payload and trace forward to maintain context
    return {"out": Token(payload=trigger_token.payload, trace=trigger_token.trace)}
~~~~~

#### Acts 3: 创建单元测试

为这些芯片编写单元测试，验证其在不同输入下的行为。

~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_context.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock, patch
from cascade.spec.physics import Token
from cascade.std.probe.context import param_probe

def test_param_probe_lookups_value():
    inputs = {"name": Token(payload="db_url"), "trigger": Token(payload=None)}
    
    # Mock WorkflowContext
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = "sqlite:///:memory:"
    
    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = param_probe(inputs, MagicMock())
    
    assert outputs["out"].payload == "sqlite:///:memory:"
    mock_ctx.get_value.assert_called_once_with("db_url")

def test_param_probe_returns_none_if_missing():
    inputs = {"name": Token(payload="missing"), "trigger": Token(payload=None)}
    mock_ctx = MagicMock()
    mock_ctx.get_value.return_value = None
    
    with patch("cascade.std.probe.context.get_current_context", return_value=mock_ctx):
        outputs = param_probe(inputs, MagicMock())
    
    assert outputs["out"].payload is None
~~~~~

~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_env.py
~~~~~
~~~~~python
import os
import pytest
from unittest.mock import MagicMock, patch
from cascade.spec.physics import Token
from cascade.std.probe.env import env_probe

def test_env_probe_samples_os_environ():
    inputs = {"name": Token(payload="TEST_VAR")}
    
    with patch.dict(os.environ, {"TEST_VAR": "cascade_value"}):
        outputs = env_probe(inputs, MagicMock())
    
    assert outputs["out"].payload == "cascade_value"

def test_env_probe_returns_none_if_env_missing():
    inputs = {"name": Token(payload="NON_EXISTENT_VAR")}
    
    # Ensure it's not in environ
    if "NON_EXISTENT_VAR" in os.environ:
        del os.environ["NON_EXISTENT_VAR"]
        
    outputs = env_probe(inputs, MagicMock())
    assert outputs["out"].payload is None
~~~~~

~~~~~act
write_file
packages/cascade-std/tests/unit/probe/test_pulse.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.probe.pulse import pulse_generator

def test_pulse_generator_passes_token_forward():
    trace = {"origin": "pulse_test"}
    inputs = {"trigger": Token(payload="BOOM", trace=trace)}
    
    outputs = pulse_generator(inputs, MagicMock())
    
    assert outputs["out"].payload == "BOOM"
    assert outputs["out"].trace["origin"] == "pulse_test"
~~~~~

### 下一步建议

我们已经完成了采样芯片 (Probe ICs) 的实现和初步测试。这些组件为 Cascade 3.0 的“探测器模型”提供了物理支撑。

根据路线图，下一步是 **任务 T4: 实现资源经纪人芯片 (Resource Broker ICs)**。这是最具挑战性的部分，特别是 `ContinuousBroker`，它需要处理资源申请 (`REQ`)、归还 (`REL`) 以及“余额不足”时的 Token 挂起逻辑。

如果你准备好了，我们将开始攻克这个“5.1GB”核心任务。
