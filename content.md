好的，遵照您的指示，我们进入 **GREEN** 阶段。我将分步实现 `Reactor` 的逻辑，并遵循您的建议，对每个函数进行独立的 `patch_file` 操作，以保持变更的原子性。

## [WIP] feat(vm): 实现 Reactor 核心循环与激发逻辑

### 用户需求
实现 `Reactor` 类的 `__init__`、`step` 和 `_fire` 方法，以满足 `test_reactor.py` 中定义的 TDD 测试用例，使其从 RED 状态转为 GREEN 状态。

### 评论
这是物理引擎的核心脉冲。通过在 `__init__` 中预处理拓扑，`step` 方法可以高效地扫描所有可能被激发的节点。`_fire` 方法则忠实地执行了“能量守恒”定律——激发必须伴随着能量（令牌）的消耗。这个实现将使我们的静态物理场第一次“动”起来。

### 目标
1.  在 `__init__` 中预编译图，构建一个从函数节点到其输入数据节点的反向索引，以优化性能。
2.  实现 `step` 方法，该方法扫描所有函数节点，并根据“全准入激发”原则确定哪些节点已就绪。
3.  实现 `_fire` 方法，该方法负责“原子性地”从所有输入槽中消耗一个令牌。
4.  确保所有单元测试通过。

### 基本原理
我们将 `Reactor` 设计为一个无状态的扫描器。
*   **预编译**: 在初始化时，我们遍历图的 `channels` 一次，构建一个 `_func_inputs` 字典，它映射了 `FuncNode ID -> List[Input DataNode IDs]`。这避免了在每个 `step()` 中重复昂贵的图遍历。
*   **扫描与激发**: `step()` 方法利用这个预编译的映射，对每个函数节点，它可以立即找到其所有输入依赖。然后，它查询 `VolatileMemory` 来检查这些输入是否都处于激发态 (`is_excited`)。
*   **能量守恒**: 对于所有就绪的节点，`_fire()` 方法被调用，它精确地从内存中 `take` 走每个输入槽的一个令牌，完成一次状态转换。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #concept/reactor #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 `__init__` 以预编译图拓扑

我们首先在 `__init__` 方法中添加图的预处理逻辑，为高效扫描做准备。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from typing import List, Set, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode
from cascade.vm.memory import VolatileMemory

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(self, graph: BipartiteGraph, memory: VolatileMemory):
        self.graph = graph
        self.memory = memory
~~~~~
~~~~~python.new
from typing import List, Set, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode
from cascade.vm.memory import VolatileMemory

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(self, graph: BipartiteGraph, memory: VolatileMemory):
        self.graph = graph
        self.memory = memory
        # Pre-compute the input data nodes for each function node for fast lookups
        self._func_inputs: Dict[str, List[str]] = {}
        self._func_nodes: List[PhysicsFuncNode] = []

        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []

        for channel in self.graph.channels:
            target_node = self.graph.nodes.get(channel.target_node_id)
            source_node = self.graph.nodes.get(channel.source_node_id)
            
            # We are interested in D -> F connections
            if isinstance(target_node, PhysicsFuncNode) and isinstance(source_node, PhysicsDataNode):
                self._func_inputs[target_node.id].append(source_node.id)
~~~~~

#### Acts 2: 实现 `step` 和 `_fire` 逻辑

现在，我们实现 `step` 的扫描逻辑和 `_fire` 的令牌消耗逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.
        
        Returns:
            int: The number of nodes that fired during this step.
        """
        raise NotImplementedError

    def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. (Future) Submits the actual payload to an Executor.
        """
        raise NotImplementedError
~~~~~
~~~~~python.new
    def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.

        Returns:
            int: The number of nodes that fired during this step.
        """
        ready_nodes: List[PhysicsFuncNode] = []
        for f_node in self._func_nodes:
            input_ids = self._func_inputs.get(f_node.id, [])
            
            # A node with no inputs is not considered ready unless explicitly defined so.
            # Our "Full-Input Firing" model means a node with inputs must have them all excited.
            if not input_ids:
                continue

            is_ready = all(self.memory.is_excited(d_node_id) for d_node_id in input_ids)

            if is_ready:
                ready_nodes.append(f_node)

        for node_to_fire in ready_nodes:
            self._fire(node_to_fire)

        return len(ready_nodes)

    def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. (Future) Submits the actual payload to an Executor.
        """
        input_ids = self._func_inputs.get(node.id, [])
        for d_node_id in input_ids:
            self.memory.take(d_node_id)
~~~~~

### 下一步建议

我们已经完成了 `Reactor` 核心调度逻辑的实现。请运行 `pytest packages/cascade-vm/tests/unit/test_reactor.py` 以确认所有测试都已通过。

一旦确认 GREEN，我们就可以继续路线图的下一项任务：**任务 1.3：实现物理执行接口**。我们将创建 `PhysicsExecutor` 并引入 `ThreadPoolExecutor`，为真正执行业务逻辑做好准备。
