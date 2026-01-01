为了在开始 5.C 阶段之前清理这个架构债务，我将生成一个计划来执行以下重构：

1.  **统一静态模型**：
    *   在 `cascade-spec` 中，删除 `PhysicsEmitterNode` 类。
    *   为 `PhysicsFuncNode` 添加一个可选的 `sink_id: Optional[str]` 字段。
    *   从 `BipartiteGraph` 中移除 `emitter_nodes` 字典。现在，发射器节点只是 `func_nodes` 字典中那些 `sink_id` 不为 `None` 的普通函数节点。
2.  **更新消费者**：
    *   修改 `Reactor` 的拓扑加载逻辑（目前未在您的代码中完全展示，但我知道它必须存在），使其在看到一个带有 `sink_id` 的 `PhysicsFuncNode` 时，能够正确实例化一个运行时的 `EmitterNode`。
    *   修改 `Reactor._fire` 逻辑，使其能正确处理 `EmitterNode`。*(注：根据您提供的 `core.py`，这部分逻辑已经存在且正确，但它依赖于 `isinstance(node, EmitterNode)`。这暂时是可接受的。)*
    *   修改编译器 `Backend`，使其在需要注入生命周期节点时，生成一个带有 `sink_id` 的 `PhysicsFuncNode`，而不是一个 `PhysicsEmitterNode`。

我将立即生成实施第一步（统一静态模型）的 Quipu 计划。这是我们能以原子方式完成的最关键的清理工作。

我将生成一个计划来解决这个问题。

## [WIP] refactor(spec): 将 PhysicsEmitterNode 统一到 PhysicsFuncNode 中

### 用户需求
在开始第 5.C 阶段之前，对代码进行审查，发现并解决 `EmitterNode` 和 `PhysicsEmitterNode` 之间存在的模式重复问题，以及其他潜在的 DRY（Don't Repeat Yourself）违规。

### 评论
这是一个非常重要的架构改进。通过将 `PhysicsEmitterNode` 的概念合并到 `PhysicsFuncNode` 中（通过一个可选的 `sink_id` 字段），我们消除了静态拓扑定义中的模式重复。这使得 `BipartiteGraph` 模型更加统一和简洁，降低了未来的维护成本，并更好地遵循了“一个发射器节点本质上只是一个具有特殊输出（Sink）的函数节点”这一核心理念。

### 目标
1.  从 `cascade.spec.topology` 中移除 `PhysicsEmitterNode` 类。
2.  在 `PhysicsFuncNode` 类中添加一个可选的 `sink_id` 字段。
3.  从 `BipartiteGraph` 的定义中移除 `emitter_nodes` 字典。

### 基本原理
当前的架构中，`PhysicsEmitterNode`（静态蓝图）和 `EmitterNode`（运行时实例）虽然职责不同，但其数据结构（Schema）几乎完全相同，这违反了 DRY 原则。

本重构通过统一静态表示来解决此问题。我们不再需要一个专门的类来表示“发射器”的静态定义。取而代之，我们将 `PhysicsFuncNode` 扩展，使其能够通过一个可选的 `sink_id` 字段来表达其“发射器”的角色。如果 `sink_id` 存在，则该节点是一个发射器；如果不存在，则它是一个普通的计算节点。

这一改变简化了 `BipartiteGraph` 的结构，使其只包含 `func_nodes` 和 `data_nodes`，从而使整个拓扑模型更加纯粹。`Reactor` 的拓扑加载逻辑（下游消费者）将负责解释这个 `sink_id` 字段，并实例化正确的运行时节点类型（`EmitterNode`）。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/vm #concept/executor #scope/core #ai/brainstorm #task/domain/architecture #task/object/topology-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `topology.py` 以统一节点定义

在此步骤中，我们将修改 `cascade.spec.topology.py` 文件。我们将移除 `PhysicsEmitterNode`，并将其功能（`sink_id`）合并到 `PhysicsFuncNode` 中。同时，我们也会更新 `BipartiteGraph` 以移除现在冗余的 `emitter_nodes` 集合。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsEmitterNode:
    """
    A specialized node that projects internal tokens to the external world.
    It acts as a boundary bridge.
    """
    current_node_instance_hash: str
    name: str
    sink_id: str  # Identifier for the external sink (e.g. "client_response")
    inputs: Dict[str, str] = field(default_factory=dict)


class ChannelKind(str, Enum):
~~~~~
~~~~~python.new
class ChannelKind(str, Enum):
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
from typing import Any

@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
    # Special lifecycle nodes
    emitter_nodes: Dict[str, PhysicsEmitterNode] = field(default_factory=dict)
~~~~~
~~~~~python.new
from typing import Any, Optional

@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
~~~~~
### 下一步建议

我们已经成功地统一了静态拓扑规范，消除了模式重复。现在，架构已经更加清晰。下一步是让系统的其他部分适配这个新的、更简洁的规范。

根据路线图，接下来的核心任务是 **5.C.1：[Compiler] 编译器后端支持信令与生命周期注入**。

在实施 5.C.1 时，你需要确保 `cascade.compiler.backend.Backend` 的 `_LifecycleInjector`（或其他相关逻辑）现在生成的是一个带有 `sink_id` 的 `PhysicsFuncNode`，而不是旧的 `PhysicsEmitterNode`。

同时，`cascade.vm.reactor.core.Reactor` 的拓扑加载逻辑（将 `BipartiteGraph` 转换为内存中的物理对象）也需要更新，以便在遇到 `sink_id` 不为 `None` 的 `PhysicsFuncNode` 时，能够正确地实例化一个运行时的 `EmitterNode`。

如果你准备好了，我们可以开始着手修改编译器后端。
