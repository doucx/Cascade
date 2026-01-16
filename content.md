我已经收到并分析了关于 `cascade-spec` 包内循环依赖和强耦合的报告。

正如你所指出的，这些问题的根源在于包内部组件之间使用了绝对导入（`cascade.spec...`），这在包初始化过程中会导致 Python 的导入机制反复尝试加载尚未完全初始化的父包。

我将按照你的建议，将 `cascade-spec` 包内的所有相关绝对导入修改为相对导入。这将打破循环路径，提高系统的稳定性。我将专注于 `cascade-spec` 包内部的修改，而不触及其他包。

## [WIP] refactor: 解耦 cascade-spec 包内的循环依赖，将绝对导入改为相对导入

### 用户需求
修复 `cascade-spec` 包内发现的强耦合组件问题，通过将绝对导入改为相对导入来解决循环依赖。

### 评论
这是一个非常关键的架构优化。在复杂的 Python 包中，尤其是那些在 `__init__.py` 中暴露大量类型的包，内部组件使用绝对导入往往是循环依赖的温床。转向相对导入是 Python 最佳实践，有助于确保包在各种环境下（尤其是作为命名空间包运行时）都能被正确加载。

### 目标
1. 遍历 `packages/cascade-spec` 中所有受影响的文件。
2. 将指向 `cascade.spec` 命名空间内部的绝对导入替换为相对导入（使用 `.` 或 `..`）。
3. 确保所有导出的符号在 `cascade/spec/__init__.py` 中仍然能够正确工作。

### 基本原理
Python 的导入机制在处理绝对导入时会检查完整的模块搜索路径并可能重新触发父包的 `__init__` 执行。而相对导入（基于 `__name__`）则允许导入器在当前包上下文中直接查找同级或上级模块，从而避免了在父包尚未加载完成时产生的不确定性循环路径。

### 标签
#intent/refine #flow/ready #priority/high #comp/interfaces #scope/core #ai/instruct #task/domain/compiler #task/object/spec-package #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修复 `cascade.spec` 根初始化文件的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from cascade.spec.ir.fingerprint import Fingerprint, InvalidFingerprintKeyError
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import (
    Token,
    PhysicsNode,
    PhysicsDataNode,
    PhysicsFuncNode,
)
from cascade.spec.physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
    RetryNode,
)
from cascade.spec.physical.topology import Channel, BipartiteGraph
from cascade.spec.physical.resources import ResourceSlot
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.spec.physical.assembly import Assembly, SymbolTable
from cascade.spec.runtime.observability import (
    EventIR,
    EventType,
    EventState,
    PhysicalAnchor,
    EventContext,
)
~~~~~
~~~~~python.new
from .ir.fingerprint import Fingerprint, InvalidFingerprintKeyError
from .physical.object import Ref
from .physical.nodes import (
    Token,
    PhysicsNode,
    PhysicsDataNode,
    PhysicsFuncNode,
)
from .physical.triad import (
    BleachNode,
    WorkerNode,
    StainNode,
    ObservabilityNode,
    RetryNode,
)
from .physical.topology import Channel, BipartiteGraph
from .physical.resources import ResourceSlot
from .physical.environment import EnvironmentDef, ResourceDef
from .physical.ports import PortRole, PortDef
from .physical.assembly import Assembly, SymbolTable
from .runtime.observability import (
    EventIR,
    EventType,
    EventState,
    PhysicalAnchor,
    EventContext,
)
~~~~~

#### Acts 2: 修复 `cascade.spec.ir` 子包的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import ArgumentKind, ArgumentDef, TaskDef
~~~~~
~~~~~python.new
from .graph import ArgumentKind, ArgumentDef, TaskDef
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
from cascade.spec.ir.fingerprint import Fingerprint
~~~~~
~~~~~python.new
from .fingerprint import Fingerprint
~~~~~

#### Acts 3: 修复 `cascade.spec.physical` 子包的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/assembly.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph
~~~~~
~~~~~python.new
from .topology import BipartiteGraph
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/nodes.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortDef
~~~~~
~~~~~python.new
from .ports import PortDef
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/resources.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import PhysicsDataNode
~~~~~
~~~~~python.new
from .nodes import PhysicsDataNode
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/topology.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import PhysicsNode
~~~~~
~~~~~python.new
from .nodes import PhysicsNode
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/triad.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import PhysicsFuncNode
~~~~~
~~~~~python.new
from .nodes import PhysicsFuncNode
~~~~~

#### Acts 4: 修复 `cascade.spec.runtime` 子包的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/compute.py
~~~~~
~~~~~python.old
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
from ..physical.object import Ref
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/storage.py
~~~~~
~~~~~python.old
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
from ..physical.object import Ref
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.interfaces import StateBackend
from cascade.spec.runtime.storage import ObjectStore
~~~~~
~~~~~python.new
from .interfaces import StateBackend
from .storage import ObjectStore
~~~~~

#### Acts 5: 修复其他子模块的导入 (Compiler, Physics)

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/compiler/interfaces.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.compiler.model import SubGraph
~~~~~
~~~~~python.new
from ..ir.graph import NodeIR
from .model import SubGraph
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/compiler/model.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
~~~~~
~~~~~python.new
from ..physical.nodes import PhysicsNode, PhysicsDataNode
from ..physical.triad import BleachNode, WorkerNode, StainNode
from ..physical.topology import Channel
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics/core.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortRole
~~~~~
~~~~~python.new
from ..physical.ports import PortRole
~~~~~

### 下一步建议
1. **验证导入**: 尝试在 Python REPL 中执行 `import cascade.spec`，确认不再抛出 `ImportError` 或因部分初始化导致的 `AttributeError`。
2. **运行测试**: 运行 `packages/cascade-spec` 相关的单元测试，确保类型和结构的逻辑仍然正确。
3. **扩展检查**: 如果本修复有效，我们应该对报告中提到的其他包（如 `cascade-vm` 和 `cascade-compiler`）也执行类似的解耦重构。
