简要回答
执行阶段 0：创建 `PortDef` 与 `PortRole` 定义，升级 `PhysicsFuncNode` 结构，并更新集成测试中的手动构图代码以匹配新规范，确立系统的 RED 状态。

## [WIP] feat(spec): implement Precision Ports (Phase 0)

### 用户需求
实施 "Cascade 3.1 路线图：精密端口" 的阶段 0。核心是消除端口定义的语义模糊性，引入 `PortDef` 和 `PortRole` 作为一等公民。

### 评论
这是一个破坏性的变更。通过修改 `cascade-spec`，我们将强制所有下游组件（Compiler, VM）在后续阶段进行适配。当前阶段的目标是建立新的“物理真理”，并更新测试代码以匹配这一新真理，从而暴露实现层面的差距（RED 状态）。

### 目标
1.  在 `cascade-spec` 中定义 `PortRole` 枚举和 `PortDef` 数据类。
2.  修改 `PhysicsFuncNode`，使其端口定义使用 `Dict[str, PortDef]` 而非 `Dict[str, str]`。
3.  更新 `cascade-compiler` 的集成测试（`test_branching`, `test_ping_pong` 等），将手动构建的节点更新为新规范。

### 基本原理
根据白皮书和新路线图，端口的角色（数据、资源、观测）必须是静态定义的物理属性，而不是运行时的隐式约定。这消除了“排除法”逻辑带来的风险，为编译器提供了更强的验证能力。

### 标签
#intent/architect #flow/ready #priority/critical #comp/spec #comp/tests #scope/core #ai/instruct #task/domain/core #task/object/ports #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 定义精密端口规范 (`cascade-spec`)

首先，我们创建新的 `ports.py` 文件来定义端口角色和结构，并将其导出。然后升级 `physics.py` 中的节点定义。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ports.py
~~~~~
~~~~~python
from enum import Enum
from dataclasses import dataclass


class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"


@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .environment import EnvironmentDef, ResourceDef

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
]
~~~~~
~~~~~python.new
from .environment import EnvironmentDef, ResourceDef
from .ports import PortRole, PortDef

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
]
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Token:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Any, Dict
from cascade.spec.ports import PortDef


@dataclass
class Token:
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
@dataclass
class PhysicsFuncNode(PhysicsNode):
    input_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""

    output_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""
~~~~~
~~~~~python.new
@dataclass
class PhysicsFuncNode(PhysicsNode):
    input_ports: Dict[str, PortDef] = field(default_factory=dict)
    """Map of port_name -> PortDef."""

    output_ports: Dict[str, PortDef] = field(default_factory=dict)
    """Map of port_name -> PortDef."""
~~~~~

#### Acts 2: 更新集成测试的手动构图 (`cascade-compiler`)

为了让测试代码符合新的 Spec 定义（避免 TypeError），我们需要更新所有手动实例化 `PhysicsFuncNode` 的测试用例。注意：此时 `Expander` 和 `Builder` 的源码尚未更新，因此这些测试在运行时可能会因为与源码不兼容而失败，或者源码生成的图结构不符合断言，这正是我们期望的 RED 状态。

**更新 `test_observability_congestion.py`**

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
import pytest
import sys
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor
~~~~~
~~~~~python.new
import pytest
import sys
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    # Producer 1
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(id="F_p1", name="P1")

    # Producer 2
    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(id="F_p2", name="P2")
~~~~~
~~~~~python.new
    # Producer 1
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(
        id="F_p1",
        name="P1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    # Producer 2
    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(
        id="F_p2",
        name="P2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(id="F_p1", name="P1")

    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(id="F_p2", name="P2")
~~~~~
~~~~~python.new
    d_in1 = PhysicsDataNode(id="D_in1", name="In1", initial_tokens=1)
    f_p1 = PhysicsFuncNode(
        id="F_p1",
        name="P1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    d_in2 = PhysicsDataNode(id="D_in2", name="In2", initial_tokens=1)
    f_p2 = PhysicsFuncNode(
        id="F_p2",
        name="P2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
~~~~~

**更新 `test_branching.py`**

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
~~~~~
~~~~~python.new
import pytest
from typing import Dict

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(id="Switch", name="SwitchNode")
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")
~~~~~
~~~~~python.new
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(
        id="Switch",
        name="SwitchNode",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")
~~~~~

**更新 `test_ping_pong.py`**

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
~~~~~
~~~~~python.new
import pytest
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
@pytest.fixture
def ping_pong_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Increment")
    d2 = PhysicsDataNode(id="D2", name="Output")

    graph = BipartiteGraph()
~~~~~
~~~~~python.new
@pytest.fixture
def ping_pong_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={"result": PortDef("result", PortRole.DATA)},
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    graph = BipartiteGraph()
~~~~~

**更新 `test_reactor.py`**

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
~~~~~
~~~~~python.new
import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.fixture
def simple_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Processor")

    # Define ports (optional for logic, but good for completeness)
    f1.input_ports["in"] = "D1"

    graph = BipartiteGraph()
~~~~~
~~~~~python.new
@pytest.fixture
def simple_topology():
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Processor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_reactor_partial_inputs():
    d1 = PhysicsDataNode(id="D1", name="Input1")
    d2 = PhysicsDataNode(id="D2", name="Input2")
    f1 = PhysicsFuncNode(id="F1", name="Processor")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, d2, f1]}
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_reactor_partial_inputs():
    d1 = PhysicsDataNode(id="D1", name="Input1")
    d2 = PhysicsDataNode(id="D2", name="Input2")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Processor",
        input_ports={
            "in1": PortDef("in1", PortRole.DATA),
            "in2": PortDef("in2", PortRole.DATA),
        },
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, d2, f1]}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(id="F1", name="Proc1")

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(id="F2", name="Proc2")

    graph = BipartiteGraph()
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_reactor_independent_nodes():
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Proc1",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(
        id="F2",
        name="Proc2",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    graph = BipartiteGraph()
~~~~~

### 下一步建议

我们已经完成了阶段 0。现在 `cascade-spec` 拥有了新的 `PortDef` 结构，测试用例中的手动构图代码也已更新。

**预期状态**:
运行测试时，`test_builder.py` 和 `test_expander.py` 应该会失败，因为源码 (`builder.py`, `expander.py`) 仍然在使用旧的 `Dict[str, str]` 赋值给 `input_ports`。手动构建图的集成测试应该通过（前提是 Reactor 不依赖端口值的具体内容，目前 Reactor 主要是基于 key 来匹配）。

接下来，我们应该进入 **阶段 1：对齐 - 重构编译器**，更新 `Expander` 和 `Builder` 以正确使用 `PortDef`。
