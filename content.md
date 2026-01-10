我们开始执行 **协议优化** 任务。为了达成 **HFEA v1.0** 定义的“定义与实现彻底解耦”，我们将核心协议和作为契约组成部分的数据模型迁移至 `cascade-spec`。

## [WIP] refactor: 迁移核心协议与模型至 spec 包

### 用户需求
将 `ReactorProtocol`、`ExpansionPolicy`、`SubGraph` 等核心协议和契约模型移动到 `cascade-spec` 中。

### 评论
当前架构中，编译器和物理引擎的契约定义散落在实现包中。这违反了“真理单一来源 (SSoT)”公理。通过将这些定义提升到 `spec` 包，我们允许：
1.  **多语言实现**：其他语言（如 Rust）可以根据 `spec` 中定义的协议实现兼容的 `Reactor`。
2.  **解耦扩展**：第三方开发者可以定义自己的 `ExpansionPolicy` 或 `Prism`，而无需依赖复杂的编译器后端实现。

### 目标
1.  **VM 协议迁移**：将 `ReactorProtocol` 和 `ComputeServiceProtocol` 移至 `cascade.spec.vm.interfaces`。
2.  **编译器模型迁移**：将 `SubGraph` 移至 `cascade.spec.compiler.model`。
3.  **编译器协议迁移**：将 `ExpansionPolicy`、`WiringPolicy` 和 `ResourcePrism` 移至 `cascade.spec.compiler.interfaces`。
4.  **更新依赖关系**：修正所有包中的导入路径。

### 标签
#intent/refine #flow/ready #priority/high
#comp/spec #comp/compiler #comp/vm #scope/dx
#task/domain/architecture #task/object/contracts #task/action/elevation
#task/state/continue

---

### Script

#### Acts 1: 在 `cascade-spec` 中建立编译器与 VM 的契约结构

我们首先在 `cascade-spec` 中创建承载这些协议的新模块。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/compiler/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel

@dataclass
class SubGraph:
    """
    A comprehensive container for all physical nodes representing a single logical task.
    It acts as the 'inventory' for the task's physical manifestation.
    """
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None

    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
    resources: Dict[str, List[PhysicsNode]] = field(default_factory=dict)
    controls: Dict[str, PhysicsNode] = field(default_factory=dict)

    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/compiler/interfaces.py
~~~~~
~~~~~python
from typing import Protocol, Any, TYPE_CHECKING
from cascade.spec.ir.graph import NodeIR
from cascade.spec.compiler.model import SubGraph

if TYPE_CHECKING:
    # Avoid circular dependency with implementation-heavy contexts
    # These will be passed as 'Any' or via Generic types in the implementation
    from cascade.compiler.backend.expansion.context import ExpansionContext
    from cascade.compiler.backend.wiring.context import WiringContext
    from cascade.spec.physical.environment import ResourceDef

class ExpansionPolicy(Protocol):
    def expand(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...

class WiringPolicy(Protocol):
    def setup_globals(self, ctx: Any) -> None: ...
    def apply(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...

class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: Any, res_def: Any) -> None: ...
    def expand_task(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any) -> None: ...
    def wire_task(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any) -> None: ...
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/vm/interfaces.py
~~~~~
~~~~~python
import asyncio
from typing import Protocol, Dict, Any, Optional

class ComputeServiceProtocol(Protocol):
    @property
    def active_count(self) -> int: ...
    def is_idle(self) -> bool: ...
    async def run(self) -> None: ...
    def stop(self) -> None: ...

class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...
    def step(self) -> int: ...
~~~~~

#### Acts 2: 更新 `cascade-compiler` 的实现以指向新契约

我们需要更新 `SubGraph` 的引用，并删除编译器内部的重复定义。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import BleacherSpec
from cascade.reflection import PhysicalIdGenerator


@dataclass
class SubGraph:
    # Interface pointers to the core triad
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None

    # Component storage for managed identity
    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
    resources: Dict[str, List[PhysicsNode]] = field(default_factory=dict)
    controls: Dict[str, PhysicsNode] = field(default_factory=dict)

    # Global index of all nodes and channels within this subgraph
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)


class Expander:
~~~~~
~~~~~python.new
from typing import List, Dict, Optional

from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.physical.nodes import PhysicsNode, PhysicsDataNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.compiler.model import SubGraph
from cascade.std.specs import BleacherSpec
from cascade.reflection import PhysicalIdGenerator


class Expander:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.py
~~~~~
~~~~~python.old
from typing import Protocol
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext


class ExpansionPolicy(Protocol):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None: ...
~~~~~
~~~~~python.new
from cascade.spec.compiler.interfaces import ExpansionPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/protocol.py
~~~~~
~~~~~python.old
from typing import Protocol
from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext


class WiringPolicy(Protocol):
    def setup_globals(self, ctx: WiringContext) -> None: ...

    def apply(
        self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None: ...
~~~~~
~~~~~python.new
from cascade.spec.compiler.interfaces import WiringPolicy
~~~~~

#### Acts 3: 更新 `cascade-vm` 指向新契约

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python.old
import asyncio
from typing import Protocol, Dict, Any, Optional


class ComputeServiceProtocol(Protocol):
    @property
    def active_count(self) -> int: ...

    def is_idle(self) -> bool: ...

    async def run(self) -> None: ...

    def stop(self) -> None: ...


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    def step(self) -> int: ...
~~~~~
~~~~~python.new
from cascade.spec.vm.interfaces import ComputeServiceProtocol, ReactorProtocol
~~~~~

### 下一步建议
我们已经完成了核心协议的迁移。这大大增强了系统的本体论正确性。下一步建议处理 **硬编码逻辑分析**：
- 在 `Machine.run` 中，目前有一个硬编码的 `asyncio.sleep(0.001)`。我们应该将其替换为一个基于状态的自适应等待机制，或者至少将其提升到配置层。
- 同时，我们可以检查 `PhysicalIdGenerator` 是否可以从 `reflection` 移动到 `spec` 或其附近，以减少语义漂移。
