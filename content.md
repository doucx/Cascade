好的，我们开始 **任务 1.2：反应堆核心循环 (The Step)**。

我们将进入 **RED** 状态。这个阶段的目标是定义 `Reactor` 的 API，并通过测试用例规定其“全准入激发”和“令牌吞噬”的核心行为。

## [WIP] test(vm): 为 Reactor.step 实现 TDD 单元测试

### 用户需求
为 `cascade-vm` 中的 `Reactor` 创建单元测试。定义 `Reactor` 如何与 `BipartiteGraph` 和 `VolatileMemory` 交互，并验证其核心循环 `step()` 的行为。

### 评论
`Reactor` 是物理场的引擎。在这一步，我们只关注它的调度逻辑，而不关注具体的代码执行。
核心测试点有三个：
1.  **全准入原则 (Full-Input Firing)**：只有当所有输入端口连接的数据节点都有令牌时，函数节点才会被激发。
2.  **原子吞噬 (Atomic Consumption)**：激发发生时，输入槽的令牌必须被瞬间消耗（从内存中移除）。
3.  **静默 (Silence)**：如果不满足条件，反应堆应保持静默，不消耗任何资源。

### 目标
1.  创建 `test_reactor.py`。
2.  定义 `Reactor` 的初始化 API：接收 `BipartiteGraph` 和 `VolatileMemory`。
3.  定义 `step()` API：执行一次扫描，返回激发的节点数量。
4.  编写测试用例覆盖：静止态、部分就绪态、完全激发态。
5.  创建一个空的 `Reactor` 类，使测试失败 (RED)。

### 基本原理
我们在测试中构建一个最小的 `D1 -> F1 -> D2` 拓扑。通过向 `D1` 放入或不放入令牌，来验证 `F1` 是否被 `Reactor` 正确地识别为 `Ready` 状态并触发 `_fire`（此时 `_fire` 负责吞噬令牌）。

### 标签
#intent/tooling #flow/ready #priority/high #comp/vm #concept/reactor #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/tdd #task/state/continue

---

### Script

#### Acts 1: 编写 Reactor 单元测试

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python
import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor

@pytest.fixture
def simple_topology():
    """
    Creates a simple D1 -> F1 topology.
    """
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Processor")
    
    # Define ports (optional for logic, but good for completeness)
    f1.input_ports["in"] = "D1"
    
    graph = BipartiteGraph()
    graph.nodes[d1.id] = d1
    graph.nodes[f1.id] = f1
    
    # Connect D1 -> F1
    channel = Channel(source_node_id=d1.id, source_port="out", target_node_id=f1.id)
    # Note: In Spec, channel is Source->Target. 
    # But wait, Topology definition says:
    # "if Source is Func, Target MUST be Data".
    # So for D -> F connection, do we have a Channel?
    # Let's check spec/topology.py.
    # Channel: source_node_id, source_port, target_node_id.
    # It seems Channel is generic.
    # But usually data flows D -> F -> D.
    # Let's assume Channel represents any directed edge in the bipartite graph.
    
    graph.channels.append(channel)
    
    return graph, d1, f1

def test_reactor_step_idle(simple_topology):
    """
    If no tokens are present, step() should do nothing.
    """
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    reactor = Reactor(graph, memory)
    
    fired_count = reactor.step()
    
    assert fired_count == 0

def test_reactor_step_fire(simple_topology):
    """
    If input has token, F1 should fire and consume the token.
    """
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    reactor = Reactor(graph, memory)
    
    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1
    
    # 2. Step
    fired_count = reactor.step()
    
    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0

def test_reactor_partial_inputs():
    """
    F1 needs D1 and D2. Only D1 has token. F1 should NOT fire.
    """
    d1 = PhysicsDataNode(id="D1", name="Input1")
    d2 = PhysicsDataNode(id="D2", name="Input2")
    f1 = PhysicsFuncNode(id="F1", name="Processor")
    
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, d2, f1]}
    
    # D1 -> F1
    graph.channels.append(Channel(d1.id, "out", f1.id))
    # D2 -> F1
    graph.channels.append(Channel(d2.id, "out", f1.id))
    
    memory = VolatileMemory()
    reactor = Reactor(graph, memory)
    
    # Only fill D1
    memory.put(d1, Token(payload="A"))
    
    fired_count = reactor.step()
    
    assert fired_count == 0
    # Token in D1 should remain untouched
    assert memory.get_count(d1.id) == 1

def test_reactor_independent_nodes():
    """
    Two independent nodes F1, F2. Both ready. Both should fire in one step.
    """
    d1 = PhysicsDataNode(id="D1", name="In1")
    f1 = PhysicsFuncNode(id="F1", name="Proc1")
    
    d2 = PhysicsDataNode(id="D2", name="In2")
    f2 = PhysicsFuncNode(id="F2", name="Proc2")
    
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, f2]}
    graph.channels.append(Channel(d1.id, "out", f1.id))
    graph.channels.append(Channel(d2.id, "out", f2.id))
    
    memory = VolatileMemory()
    reactor = Reactor(graph, memory)
    
    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))
    
    fired_count = reactor.step()
    
    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0
~~~~~

#### Acts 2: 创建 Reactor API 桩 (Entering RED)

创建 `reactor.py`，定义接口，抛出 `NotImplementedError`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python
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

### 下一步建议

现在运行 `pytest packages/cascade-vm/tests/unit/test_reactor.py` 应该会失败。

接下来的 **GREEN** 阶段任务：
1.  在 `Reactor.__init__` 中预处理图结构，建立反向索引（Inverse Index），即 `FunctionNode_ID -> List[Input_DataNode_ID]`。这是为了快速检查 `is_ready`，避免每次 `step` 都遍历 `channels` 列表。
2.  实现 `step()` 方法：遍历所有 `PhysicsFuncNode`，检查其所有输入 `DataNode` 是否 `is_excited`。
3.  实现 `_fire()` 方法：遍历输入节点，调用 `memory.take()` 吞噬令牌，并简单打印日志。
4.  确保测试通过。
