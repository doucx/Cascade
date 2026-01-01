## [WIP] feat(spec): 实施 Cascade 3.0 创世纪阶段的核心定义

### 用户需求
根据 Cascade 3.0 路线图的“阶段 0：创世纪 (Genesis)”要求，一次性创建所有定义物理世界基本粒子的接口文件。这包括物理节点、令牌结构、三连体协议、拓扑容器以及资源定义。

### 评论
这是“全对称计算物理场”的基石。我们将在这个阶段确立不可动摇的物理定律（Spec）。所有的定义都将是纯粹的数据结构（Dataclass），严禁包含任何运行时逻辑。这些定义将成为后续 Compiler（造物主）和 VM（引擎）之间唯一的通用语言。

### 目标
1.  创建 `physics.py`: 定义 `Token`, `PhysicsNode`, `PhysicsDataNode`, `PhysicsFuncNode`。
2.  创建 `triad.py`: 定义执行三连体 `BleachNode`, `WorkerNode`, `StainNode` 以及 `ObservabilityNode`。
3.  创建 `topology.py`: 定义 `Channel` 和 `BipartiteGraph`。
4.  创建 `resources.py`: 定义 `ResourceSlot`。
5.  更新 `__init__.py`: 导出上述核心原语。

### 基本原理
我们严格遵循“真理之源”原则，将所有物理实体的定义集中在 `cascade-spec` 包中。
*   **物理化**: 通过 `Token` 的 `trace` 字段和 `Channel` 的 `tag_filter` 字段，我们将控制流和可观测性内化为物理对象的属性。
*   **三连体**: 通过显式定义 `Bleach` (漂白) 和 `Stain` (染色) 节点，我们在协议层面强制了解耦业务逻辑与环境上下文。
*   **静态类型**: 使用 `dataclasses` 确保所有定义都是静态的、可序列化的、且对类型检查器友好的。

### 标签
#intent/architect #flow/ready #priority/high #comp/spec #concept/physics #scope/core #ai/instruct #task/domain/core #task/object/spec-genesis #task/action/define #task/state/continue

---

### Script

#### Acts 1: 定义物理基础粒子 (Physics)

创建 `physics.py`，定义流动的能量（Token）和静止的物质（Nodes）。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Token:
    """
    The fundamental unit of energy and information flow in the physics field.
    """

    payload: Any
    """The actual data being transferred (Business Value)."""

    tag: str = "default"
    """Routing tag used by Channels to filter tokens (Control Signal)."""

    trace: Dict[str, Any] = field(default_factory=dict)
    """
    Metadata accumulator for observability and context propagation.
    Contains timestamp, source_id, retry_counts, etc.
    """


@dataclass
class PhysicsNode:
    """
    Base class for all static entities in the bipartite graph.
    """

    id: str
    """
    The canonical structural identifier.
    Naming Convention: [State]_[Source]_[Object]_hash
    """

    name: str
    """Human-readable name for debugging and visualization."""


@dataclass
class PhysicsDataNode(PhysicsNode):
    """
    Represents a storage location (Place) in the Petri net.
    It holds Tokens.
    """

    capacity: int = 1
    """Maximum number of tokens this node can hold simultaneously."""


@dataclass
class PhysicsFuncNode(PhysicsNode):
    """
    Represents a transformation unit (Transition) in the Petri net.
    It consumes Tokens from inputs and produces Tokens to outputs.
    """

    input_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""

    output_ports: Dict[str, str] = field(default_factory=dict)
    """Map of port_name -> description/type."""
~~~~~

#### Acts 2: 定义三连体微观结构 (Triad)

创建 `triad.py`，定义构成一个逻辑任务的微观物理节点类型。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/triad.py
~~~~~
~~~~~python
from dataclasses import dataclass
from .physics import PhysicsFuncNode


@dataclass
class BleachNode(PhysicsFuncNode):
    """
    F_pre: The Pre-process Node.
    Responsible for:
    1. Waiting for all inputs (Data, Control, Resources).
    2. 'Bleaching' tokens: stripping metadata to extract pure payload.
    3. Emitting start events to the sidecar observation channel.
    """

    pass


@dataclass
class WorkerNode(PhysicsFuncNode):
    """
    F_exec: The Execution Node.
    Responsible for:
    1. Executing the pure business logic (Python function).
    2. Producing a pure result.
    It is completely unaware of tags, traces, or the graph topology.
    """

    pass


@dataclass
class StainNode(PhysicsFuncNode):
    """
    F_post: The Post-process Node.
    Responsible for:
    1. 'Staining' the result: wrapping it into a new Token with tags and trace info.
    2. Routing based on results (setting tags).
    3. Emitting end events to the sidecar observation channel.
    """

    pass


@dataclass
class ObservabilityNode(PhysicsFuncNode):
    """
    F_obs: The Sidecar Observer.
    Responsible for converting raw trace tokens into standardized telemetry events
    and publishing them to the external message bus.
    """

    pass
~~~~~

#### Acts 3: 定义拓扑容器 (Topology)

创建 `topology.py`，定义连接节点的通道和整个图结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .physics import PhysicsNode


@dataclass
class Channel:
    """
    A directed connection between a Function Node and a Data Node.
    """

    source_node_id: str
    """The ID of the upstream node."""

    source_port: str
    """The name of the output port on the source node."""

    target_node_id: str
    """
    The ID of the downstream node.
    Note: In a bipartite graph, if Source is Func, Target MUST be Data.
    """

    tag_filter: Optional[str] = None
    """
    If set, this channel only accepts Tokens with a matching tag.
    This acts as a spectral filter for control flow.
    """


@dataclass
class BipartiteGraph:
    """
    The static, physical representation of the computational field.
    """

    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    """All physical nodes indexed by their ID."""

    channels: List[Channel] = field(default_factory=list)
    """All connections between nodes."""
~~~~~

#### Acts 4: 定义资源 (Resources)

创建 `resources.py`，定义资源槽位。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/resources.py
~~~~~
~~~~~python
from dataclasses import dataclass
from .physics import PhysicsDataNode


@dataclass
class ResourceSlot(PhysicsDataNode):
    """
    A special DataNode that holds 'Permission Tokens' representing system resources
    (e.g., Concurrency Slots, GPU locks).
    Used to implement back-pressure and resource constraints topologically.
    """

    pass
~~~~~

#### Acts 5: 导出定义

更新 `cascade-spec` 的入口，使其易于导入。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python
from .fingerprint import Fingerprint, InvalidFingerprintKeyError
from .physics import Token, PhysicsNode, PhysicsDataNode, PhysicsFuncNode
from .triad import BleachNode, WorkerNode, StainNode, ObservabilityNode
from .topology import Channel, BipartiteGraph
from .resources import ResourceSlot

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
]
~~~~~

### 下一步建议
我们已经完成了 Spec 的定义。现在物理世界的“法律”已经确立，下一步是构建能够运行这个世界的“引擎”。

建议进入 **阶段 1：反应堆点火 (Reactor Ignition)**。
具体包括：
1.  在 `cascade-vm` 中实现 `VolatileMemory`，用于管理 `DataNode` 的状态。
2.  实现 `Reactor` 的核心循环 `step()` 和 `_fire()` 逻辑。
3.  实现 `PhysicsExecutor`，让三连体能够真正动起来。
