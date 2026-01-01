好的，我们正式进入 **任务 1.4：集成测试 (Ping-Pong)** 的 **RED** 阶段。

这是至关重要的一步，我们将首次把 `VolatileMemory`、`Reactor` 和 `PhysicsExecutor` 三个核心组件组合在一起，定义它们协作的最终行为。

## [WIP] test(vm): 为端到端 Ping-Pong 流程创建集成测试

### 用户需求
为 `cascade-vm` 创建一个集成测试，模拟一个完整的 `D1 -> F1 -> D2` (Ping-Pong) 工作流。该测试将定义 `Reactor` 如何利用 `PhysicsExecutor` 执行与 `PhysicsFuncNode` 关联的 Python 函数，并将结果放入下游的 `PhysicsDataNode`。

### 评论
这个测试是 Cascade 3.0 物理引擎的“冒烟测试”。它不再关注单个组件的内部逻辑，而是验证整个物理定律系统是否自洽：能量（令牌）是否能从一个地方流动到另一个地方，并在途中被正确地转化。这个测试的通过，将证明我们的核心物理模型是可行的。

### 目标
1.  创建 `tests/integration` 目录和 `test_ping_pong.py` 文件。
2.  定义一个 `pytest` fixture，用于构建一个包含 `D1`, `F1`, `D2` 节点以及 `D1->F1` 和 `F1->D2` 连接的 `BipartiteGraph`。
3.  在测试中，定义一个 `Reactor` 与 `F1` 节点的函数逻辑之间的映射关系。
4.  编写测试用例：向 `D1` 放入令牌，`await reactor.step()`，然后断言 `D2` 中收到了经过函数处理后的新令牌。
5.  更新 `Reactor` 的 API 签名以接受 `PhysicsExecutor` 和函数映射，并将其方法改为 `async`，使其因 `NotImplementedError` 而失败。

### 基本原理
我们遵循 TDD 原则，先定义期望的最终行为。测试将失败，因为它要求 `Reactor` 具备当前版本所没有的能力：
*   **函数绑定**: `Reactor` 需要知道 `F1` 节点对应哪个 Python 函数。我们将通过一个 `function_map` 字典在运行时注入这个绑定关系。
*   **异步执行**: `Reactor` 的 `step` 和 `_fire` 必须是 `async` 的，因为它需要 `await` `PhysicsExecutor` 的结果。
*   **结果路由**: `_fire` 方法不仅要消耗输入令牌，还必须知道将执行结果放入哪个输出 `DataNode`（即 `D2`）。

### 标签
#intent/tooling #flow/ready #priority/high #comp/vm #concept/reactor #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/integration-test #task/action/tdd #task/state/continue

---

### Script

#### Acts 1: 创建集成测试目录

首先，我们为集成测试建立必要的目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/tests/integration
touch packages/cascade-vm/tests/integration/__init__.py
~~~~~

#### Acts 2: 编写 Ping-Pong 集成测试

这是定义我们最终目标的测试文件。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python
import pytest
from typing import Dict, Callable

from cascade.spec.physics import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor

def simple_increment(val: int) -> int:
    """The business logic for our F1 node."""
    return val + 1

@pytest.fixture
def ping_pong_topology():
    """
    Creates a D1 -> F1 -> D2 topology.
    """
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(id="F1", name="Increment")
    d2 = PhysicsDataNode(id="D2", name="Output")
    
    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2]}
    
    # D1 -> F1
    graph.channels.append(Channel(source_node_id=d1.id, source_port="value", target_node_id=f1.id))
    # F1 -> D2
    graph.channels.append(Channel(source_node_id=f1.id, source_port="result", target_node_id=d2.id))
    
    # The runtime binding between the abstract physics node and the concrete function
    function_map: Dict[str, Callable] = {
        f1.id: simple_increment
    }
    
    return graph, d1, f1, d2, function_map

@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    """
    Tests the full end-to-end flow:
    1. A token is placed in D1.
    2. Reactor.step() is called.
    3. F1 should fire, consuming the token from D1.
    4. PhysicsExecutor runs the increment function.
    5. A new token with the result is placed in D2.
    """
    graph, d1, f1, d2, function_map = ping_pong_topology
    
    memory = VolatileMemory()
    executor = PhysicsExecutor()
    reactor = Reactor(graph, memory, executor, function_map)
    
    # 1. Start state
    initial_token = Token(payload=10)
    memory.put(d1, initial_token)
    
    # 2. Run the physics simulation for one step
    fired_count = await reactor.step()
    
    # 3. Assertions
    assert fired_count == 1
    
    # Input token should be consumed
    assert memory.get_count(d1.id) == 0
    
    # Output node should receive the result
    assert memory.get_count(d2.id) == 1
    
    result_token = memory.take(d2.id)
    assert result_token.payload == 11 # 10 + 1
~~~~~

#### Acts 3: 更新 Reactor API 桩 (Entering RED)

为了让测试失败，我们将更新 `Reactor` 的 `__init__` 签名以接受新依赖，并将 `step` 和 `_fire` 改为 `async`，但保留 `NotImplementedError`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
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
~~~~~python.new
from typing import List, Callable, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        
        # Pre-compute the input/output data nodes for each function node
        self._func_inputs: Dict[str, List[str]] = {}
        self._func_outputs: Dict[str, List[str]] = {}
        self._func_nodes: List[PhysicsFuncNode] = []

        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []
                self._func_outputs[node.id] = []

        for channel in self.graph.channels:
            target_node = self.graph.nodes.get(channel.target_node_id)
            source_node = self.graph.nodes.get(channel.source_node_id)
            
            # D -> F connections define inputs
            if isinstance(target_node, PhysicsFuncNode) and isinstance(source_node, PhysicsDataNode):
                self._func_inputs[target_node.id].append(source_node.id)
            
            # F -> D connections define outputs
            elif isinstance(source_node, PhysicsFuncNode) and isinstance(target_node, PhysicsDataNode):
                self._func_outputs[source_node.id].append(target_node.id)

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

### 下一步建议

我们已经定义了端到端集成测试，并通过更新 `Reactor` 的 API 使其处于 **RED** 状态。现在，是时候让它变绿了。

接下来的 **GREEN** 阶段任务：
1.  修改 `Reactor.step` 方法，使其能够处理 `asyncio.gather` 来并行激发多个就绪的节点。
2.  在 `_fire` 方法中，实现完整的逻辑：
    *   从内存中 `take` 所有输入令牌。
    *   提取 `payload` 并作为参数。
    *   调用 `self.executor.submit` 执行函数。
    *   创建一个新的 `Token` 来包裹结果。
    *   将新令牌 `put` 到所有输出 `DataNode` 的内存槽中。
3.  确保集成测试和所有单元测试都通过。
