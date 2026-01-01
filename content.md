## [WIP] feat(vm): 实现 Reactor 并行激发与执行逻辑

### 用户需求
1. 修复 `packages/cascade-vm/tests/unit/test_reactor.py` 中的单元测试，使其适配 `Reactor` 类的新 API 签名（需要 `executor` 和 `function_map`），并支持异步调用。
2. 实现 `Reactor.step` 和 `Reactor._fire` 方法，支持基于 `asyncio` 的并行激发，以及通过 `PhysicsExecutor` 执行实际业务逻辑，从而通过集成测试 `test_ping_pong.py`。

### 评论
我们正处于“点火”的关键时刻。
首先，必须偿还因 API 变更（引入 `PhysicsExecutor` 和异步化）导致的技术债务，修复单元测试。
其次，在 `Reactor` 的实现中，我们将把静态的拓扑结构与动态的执行能力结合起来。`step` 方法将从单线程顺序扫描进化为基于 `asyncio.gather` 的并行激发，这直接体现了物理场的并发特性。`_fire` 方法将完成“物质-能量-物质”的转化循环：消耗输入 Token -> 释放能量（执行函数） -> 产生新 Token。

### 目标
1.  更新 `test_reactor.py`，引入 `PhysicsExecutor` 和 Dummy 函数，将测试用例转换为 `async` 模式。
2.  在 `reactor.py` 中引入 `asyncio`。
3.  实现 `Reactor.step`：识别就绪节点，使用 `asyncio.gather` 并行触发 `_fire`。
4.  实现 `Reactor._fire`：消耗输入令牌，从 `function_map` 查找函数，提交给 `executor`，并将结果封装为新令牌推送到输出节点。

### 基本原理
*   **并行性**: 利用 `asyncio.gather`，物理引擎可以在同一时间步内激发所有就绪的节点，最大化吞吐量。
*   **数据流**: 输入参数通过列表收集 (`[t.payload for t in tokens]`) 传递给函数。这是一个简单的位置参数映射，足以满足目前的 Ping-Pong 需求。
*   **输出广播**: 函数的返回值被封装为 Token 后，会被复制并分发到所有连接的输出节点，模拟了信号的广播特性。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #concept/reactor #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 修复 Reactor 单元测试

我们将更新 `test_reactor.py` 以匹配新的 `Reactor` 构造函数签名，并将测试用例改为异步。

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
~~~~~python.new
import pytest
from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.executor import PhysicsExecutor

# Dummy function for testing
def noop(*args):
    return "result"

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
    graph.channels.append(channel)
    
    return graph, d1, f1

@pytest.mark.asyncio
async def test_reactor_step_idle(simple_topology):
    """
    If no tokens are present, step() should do nothing.
    """
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)
    
    fired_count = await reactor.step()
    
    assert fired_count == 0

@pytest.mark.asyncio
async def test_reactor_step_fire(simple_topology):
    """
    If input has token, F1 should fire and consume the token.
    """
    graph, d1, f1 = simple_topology
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)
    
    # 1. Put token
    memory.put(d1, Token(payload="energy"))
    assert memory.get_count(d1.id) == 1
    
    # 2. Step
    fired_count = await reactor.step()
    
    # 3. Assertions
    assert fired_count == 1
    # Token must be consumed (Atomic Consumption)
    assert memory.get_count(d1.id) == 0

@pytest.mark.asyncio
async def test_reactor_partial_inputs():
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
    executor = PhysicsExecutor()
    function_map = {f1.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)
    
    # Only fill D1
    memory.put(d1, Token(payload="A"))
    
    fired_count = await reactor.step()
    
    assert fired_count == 0
    # Token in D1 should remain untouched
    assert memory.get_count(d1.id) == 1

@pytest.mark.asyncio
async def test_reactor_independent_nodes():
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
    executor = PhysicsExecutor()
    function_map = {f1.id: noop, f2.id: noop}
    reactor = Reactor(graph, memory, executor, function_map)
    
    memory.put(d1, Token("A"))
    memory.put(d2, Token("B"))
    
    fired_count = await reactor.step()
    
    assert fired_count == 2
    assert memory.get_count(d1.id) == 0
    assert memory.get_count(d2.id) == 0
~~~~~

#### Acts 2: 实现 Reactor 逻辑

实现 `Reactor` 的 `step` 和 `_fire` 方法，引入 `asyncio`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from typing import List, Callable, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

class Reactor:
~~~~~
~~~~~python.new
import asyncio
from typing import List, Callable, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

class Reactor:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    async def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.
        
        Returns:
            int: The number of nodes that fired during this step.
        """
        raise NotImplementedError

    async def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. Submits the actual payload to an Executor.
        3. Puts the resulting token into the output slots.
        """
        raise NotImplementedError
~~~~~
~~~~~python.new
    async def step(self) -> int:
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

        if not ready_nodes:
            return 0

        # Fire all ready nodes in parallel
        await asyncio.gather(*(self._fire(node) for node in ready_nodes))

        return len(ready_nodes)

    async def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. Submits the actual payload to an Executor.
        3. Puts the resulting token into the output slots.
        """
        # 1. Consume inputs
        input_ids = self._func_inputs.get(node.id, [])
        input_tokens = [self.memory.take(d_node_id) for d_node_id in input_ids]
        args = [t.payload for t in input_tokens]

        # 2. Execute
        func = self.function_map.get(node.id)
        if not func:
            # In a robust system, this might log an error or emit an error token.
            # For now, we raise to fail fast during testing.
            raise ValueError(f"No function mapped for node {node.id}")

        result_payload = await self.executor.submit(func, tuple(args))

        # 3. Produce outputs
        output_ids = self._func_outputs.get(node.id, [])
        # In a real Triad, StainNode would handle wrapping.
        # Here we create a simple token.
        output_token = Token(payload=result_payload)

        for out_id in output_ids:
            # We need the PhysicsDataNode object to call put.
            # Since we pre-validated topology in __init__, we can safely access nodes.
            out_node = self.graph.nodes[out_id]
            # Ensure it is a DataNode to satisfy type checker (though logic guarantees it)
            if isinstance(out_node, PhysicsDataNode):
                self.memory.put(out_node, output_token)
~~~~~

### 下一步建议

我们已经完成了 `Reactor` 的实现和单元测试的修复。
请运行 `pytest packages/cascade-vm/tests`，验证：
1.  单元测试 `test_executor.py`, `test_memory.py`, `test_reactor.py` 全部通过。
2.  集成测试 `test_ping_pong.py` 通过。

如果一切顺利，说明 **阶段 1：反应堆点火** 已圆满完成。
接下来的 **阶段 2：微指令集构建 (Instruction Set Architecture)** 将引导我们深入实现三连体中的 `Bleacher`（漂白器）和 `Stainer`（染色器），这将涉及到对 `Token` 的元数据处理和更复杂的参数解析逻辑。
