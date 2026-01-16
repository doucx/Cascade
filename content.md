我已经收到了关于 `cascade-compiler` 包的深度耦合分析报告。

这个包的情况最为复杂，因为编译器的后端逻辑（Expansion 和 Wiring）是高度交错的：Expansion 策略需要了解 Wiring 容器，而 Wiring 策略又依赖于 Expansion 阶段产生的 `SubGraph` 结构。这种“策略间引用”在绝对导入模式下，会导致 Python 在试图解析 `cascade.compiler.backend.builder` 时，陷入一个巨大的、包含 16 个文件的模块初始化环。

我将按照之前的成功实践，系统性地将 `cascade-compiler` 内部的所有绝对导入重写为相对导入。这将确保无论从哪个入口（Builder、Generator 或单独的策略）进入，包都能在局部上下文内安全加载。

## [WIP] refactor: 解耦 cascade-compiler 包内的循环依赖，重构导入路径

### 用户需求
修复 `cascade-compiler` 包内发现的 16 个文件组成的强耦合组件问题，通过将绝对导入（`cascade.compiler...`）改为相对导入来彻底解决初始化循环。

### 评论
`cascade-compiler` 是整个系统的“织网者”。目前其内部策略（Policies）和上下文（Contexts）之间通过绝对导入形成的硬耦合，使得任何局部的架构调整都可能引发全局的导入失败。将其重构为相对导入，不仅是为了修复当前的循环依赖，更是为了实现编译组件的物理位置透明性，为未来的插件化和动态策略加载打下基础。

### 目标
1. 将 `backend/expansion/policies` 下的所有绝对导入改为相对导入。
2. 将 `backend/wiring/policies` 和 `backend/wiring/prisms` 下的所有绝对导入改为相对导入。
3. 修正 `backend/builder.py` 中的大量策略引入路径。
4. 确保 `ExpansionContext` 和 `WiringContext` 之间的引用关系不会触发包根重载。

### 基本原理
在大型复杂的包中，相对导入通过 `.` (同级), `..` (上级), `...` (上上级) 建立模块间的拓扑联系。这种方式不依赖于包在 `sys.path` 中的根路径名，能够有效规避 Python 在处理“部分初始化模块”（Partially Initialized Modules）时的局限性。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/compiler #task/object/compiler-package #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 Expansion 策略及其上下文的导入

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/context.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.ir.graph import GraphIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring import WiringHarness


@dataclass
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.ir.graph import GraphIR
from ..expander import SubGraph
from ..wiring import WiringHarness


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import EgressSpec
from cascade.spec.physical.constants import NodePrefix
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~
~~~~~python.new
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import EgressSpec
from cascade.spec.physical.constants import NodePrefix
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.reflection import PhysicalIdGenerator
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
from cascade.compiler.backend.wiring.prism import ResourcePrism
from cascade.compiler.backend.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from ...expander import SubGraph
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy
from ...wiring.prism import ResourcePrism
from ...wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
~~~~~

#### Acts 2: 修复 Wiring 策略及其上下文的导入

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/context.py
~~~~~
~~~~~python.old
from dataclasses import dataclass

from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext


@dataclass
~~~~~
~~~~~python.new
from dataclasses import dataclass

from ..expander import SubGraph
from ..expansion.context import ExpansionContext


@dataclass
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prism.py
~~~~~
~~~~~python.old
from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.context import ExpansionContext


class ResourcePrism(Protocol):
~~~~~
~~~~~python.new
from typing import Protocol, Any
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from ..expander import SubGraph
from .context import WiringContext
from ..expansion.context import ExpansionContext


class ResourcePrism(Protocol):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.wiring.prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
~~~~~
~~~~~python.new
from cascade.std.resource.discrete import DiscreteLedger
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from ...expansion.context import ExpansionContext
from ..prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import StainerSpec, BleacherSpec, EgressSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import StainerSpec, BleacherSpec, EgressSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.std.specs import ObservabilitySpec, BleacherSpec, StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.std.specs import ObservabilitySpec, BleacherSpec, StainerSpec
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.std.specs import StainerSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import BleacherSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import BleacherSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/resource.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
from cascade.compiler.backend.wiring.prism import ResourcePrism
from cascade.compiler.backend.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy
from ..prism import ResourcePrism
from ..prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
~~~~~

#### Acts 3: 修复 Builder 的导入路径

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.expansion.policies.parameter import (
    ParameterExpansionPolicy,
)
from cascade.compiler.backend.expansion.policies.control import (
    ControlFlowExpansionPolicy,
)
from cascade.compiler.backend.expansion.policies.pulse import PulseExpansionPolicy
from cascade.compiler.backend.expansion.policies.resource import (
    ResourceExpansionPolicy,
)
from cascade.compiler.backend.wiring.policies.parameter import ParameterWiringPolicy
from cascade.compiler.backend.wiring.policies.control import ControlFlowWiringPolicy
from cascade.compiler.backend.wiring.policies.observability import (
    ObservabilityWiringPolicy,
)
from cascade.compiler.backend.wiring.policies.resource import ResourceWiringPolicy
from cascade.compiler.backend.wiring.policies.pulse import PulseWiringPolicy
from cascade.spec.physical.constants import NodePrefix
~~~~~
~~~~~python.new
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from .wiring.context import WiringContext
from .expansion.policies.parameter import (
    ParameterExpansionPolicy,
)
from .expansion.policies.control import (
    ControlFlowExpansionPolicy,
)
from .expansion.policies.pulse import PulseExpansionPolicy
from .expansion.policies.resource import (
    ResourceExpansionPolicy,
)
from .wiring.policies.parameter import ParameterWiringPolicy
from .wiring.policies.control import ControlFlowWiringPolicy
from .wiring.policies.observability import (
    ObservabilityWiringPolicy,
)
from .wiring.policies.resource import ResourceWiringPolicy
from .wiring.policies.pulse import PulseWiringPolicy
from cascade.spec.physical.constants import NodePrefix
~~~~~

### 下一步建议
1. **编译器冒烟测试**: 创建一个简单的 DSL 任务，通过 `Builder().build(ir, env)` 验证整个编译管线是否能无阻塞运行。
2. **符号表检查**: 确保 `CompilationArtifact` 中的 `symbol_table` 能够正确映射到物理 Node ID，没有因为导入方式改变而导致类型识别错误。
3. **完成最后两个强耦合组件**: 解决 `cascade-runtime` (8个文件) 和 `cascade-sdk` (3个文件) 的耦合问题。
