好的，我们继续执行路线图，进入 **阶段 5.B.2**。

这一步的目标是实现架构的纯粹性：我们将彻底移除 `TerminatorNode` 这一特殊概念。`Reactor` 将不再需要知道任何关于“生命周期”的特殊规则，它将演变成一个更加通用的物理引擎。

## [WIP] refactor(vm, spec): 废除 TerminatorNode 及其在 Reactor 中的特殊逻辑

### 用户需求
根据 [路线图：全对称物理引擎与编译器重构](深度重构/路线图：全对称物理引擎与编译器重构.md)，执行阶段 5.B.2，即从 `cascade-spec` 和 `cascade-vm` 中彻底移除 `TerminatorNode` 及其相关的特殊处理逻辑。

### 评论
这是一个至关重要的架构简化步骤。`TerminatorNode` 的存在迫使 `Reactor` 内部需要一个特殊的 `if/else` 分支，这破坏了物理引擎的通用性。移除它，我们将强制实现“控制反转”——`Reactor` 只负责执行，而“停止”这个决策将由外部策略通过监听一个普通的 `EmitterNode` 来实现。这使得 `Reactor` 更加纯粹、可复用，并与生命周期管理完全解耦。

### 目标
1.  从 `cascade.spec.physics` 中删除 `TerminatorNode` 的定义。
2.  从 `cascade.spec.topology` 中删除 `PhysicsTerminatorNode` 的定义及其在 `BipartiteGraph` 中的引用。
3.  从 `Reactor._fire` 方法中移除处理 `TerminatorNode` 的硬编码逻辑。
4.  删除专门测试 `TerminatorNode` 行为的 `test_autonomous_lifecycle.py` 文件，因为它现在已经过时。

### 基本原理
我们遵循“代码即物理”的原则。一个物理引擎不应该为某个特定的粒子（节点）设置特殊的宇宙法则。通过移除 `TerminatorNode`，我们消除了这种特殊性。`Reactor` 将对所有 `FuncNode` 一视同仁，只负责根据输入激发它们并提交给执行器。图的“终结”将不再是 `Reactor` 的内部职责，而是计算图拓扑本身通过 `EmitterNode` 与外部世界通信所产生的自然结果。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #concept/state #scope/core #dx
#ai/instruct
#task/domain/vm #task/object/terminator-node #task/action/removal
#task/state/continue

---

### Script

#### Acts 1: 从 `spec.physics` 中移除 `TerminatorNode`

我们首先从底层的物理模型定义中删除 `TerminatorNode` 类。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    pass


class EmitterNode(FuncNode):
~~~~~
~~~~~python.new
class EmitterNode(FuncNode):
~~~~~

#### Acts 2: 从 `spec.topology` 中移除 `PhysicsTerminatorNode`

接着，我们从静态拓扑定义中移除 `PhysicsTerminatorNode` 以及它在 `BipartiteGraph` 中的字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsTerminatorNode:
    """
    A special Functional Node that, when fired, triggers the shutdown of the Reactor.
    It represents the "End of Time" for a run.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicsEmitterNode:
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsEmitterNode:
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
    # Special lifecycle nodes
    terminator_nodes: Dict[str, PhysicsTerminatorNode] = field(default_factory=dict)
    emitter_nodes: Dict[str, PhysicsEmitterNode] = field(default_factory=dict)
~~~~~
~~~~~python.new
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
    # Special lifecycle nodes
    emitter_nodes: Dict[str, PhysicsEmitterNode] = field(default_factory=dict)
~~~~~

#### Acts 3: 从 `Reactor` 中移除特殊处理逻辑

现在，我们移除 `Reactor` 核心循环中对 `TerminatorNode` 的特殊判断，使其成为一个纯粹的执行循环。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode, Token
~~~~~
~~~~~python.new
from cascade.spec.physics import DataNode, FuncNode, EmitterNode, Token
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, TerminatorNode):
            self.stop()
            # A terminator can also signal, e.g., to confirm shutdown.
            # For now, we assume it's the absolute end.
            return
        
        if isinstance(node, EmitterNode):
~~~~~
~~~~~python.new
        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, EmitterNode):
~~~~~

#### Acts 4: 删除过时的生命周期测试

`test_autonomous_lifecycle.py` 测试文件是专门为验证 `TerminatorNode` 的行为而设计的。既然该功能已被移除，此测试也必须被删除。

~~~~~act
delete_file
packages/cascade-vm/tests/reactor/test_autonomous_lifecycle.py
~~~~~

### 下一步建议
我们已经成功地将 `Reactor` 从生命周期管理的职责中解放出来。现在，我们需要提供替代的机制来与外部世界通信和控制执行流程。

根据路线图，下一步是 **阶段 5.B.3：[VM] 实现 `EmitterNode`**。我将准备一个计划来实现 `EmitterNode` 的功能，包括在 `Reactor` 中注册 `sink` 回调，并在 `EmitterNode` 被激发时调用它们。这将是重建生命周期控制的第一步。
