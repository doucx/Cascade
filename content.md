## [WIP] test(compiler): 修复因资源协商重构导致的测试失败

### 用户需求
修复 `test_builder_environment.py` 和 `test_resource_backpressure.py` 中的断言错误。

### 评论
**错误分析**:
1.  **`test_builder_environment` 失败**: 之前的测试假设 Builder 会生成 `canonical.resource.gpu` (D_res) 节点。但现在 Builder 生成的是 `canonical.resource.broker.gpu` (F_broker) 和 `canonical.resource.ledger.gpu` (D_ledger) 以及相关的 Buffer。旧的断言已经过时。
2.  **`test_resource_backpressure` 失败**: 同样是因为节点 ID 和图结构的改变。测试试图查找旧的 D_res，而且由于图结构变得更加复杂（引入了 IC），我们需要更新 `function_map` 的映射逻辑，将新生成的物理节点 ID 映射到对应的 Python 函数实现。

### 目标
1.  更新 `test_builder_environment.py`：断言新的 Broker 和 Ledger 节点结构。
2.  更新 `test_resource_backpressure.py`：
    *   适应新的物理图结构（Broker, Requestor, Probe）。
    *   正确配置 `function_map`，导入并映射 `discrete_broker`, `resource_requestor`, `const_probe`。
    *   调整对“资源占用”状态的断言方式（检查 Ledger 而不是 D_res）。

### 基本原理
测试必须反映架构的演进。既然我们已经将物理层升级为 IC 化的协商网络，测试用例就必须验证这个新网络的正确性。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/compiler #scope/core #ai/instruct #task/domain/testing #task/object/integration-test #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 Builder 单元测试

更新断言以匹配 Broker/Ledger 结构。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python.old
def test_builder_creates_resources_from_env(simple_graph_ir):
    # 1. Define Environment with 'gpu'
    env = EnvironmentDef(
        resources=[
            ResourceDef(name="gpu", capacity=4),
            ResourceDef(name="cpu", capacity=8),  # Unused resource
        ]
    )

    # 2. Build (Expect this to fail currently due to signature mismatch)
    builder = Builder()
    graph = builder.build(simple_graph_ir, environment=env)

    # 3. Assert D_res creation
    # Used resource should exist
    assert "canonical.resource.gpu" in graph.nodes
    gpu_node = graph.nodes["canonical.resource.gpu"]
    assert gpu_node.capacity == 4
    # Initial tokens should match capacity (potential energy)
    assert gpu_node.initial_tokens == 4

    # Unused resource should ALSO exist (Physics is objective)
    assert "canonical.resource.cpu" in graph.nodes
    cpu_node = graph.nodes["canonical.resource.cpu"]
    assert cpu_node.capacity == 8
~~~~~
~~~~~python.new
def test_builder_creates_resources_from_env(simple_graph_ir):
    # 1. Define Environment with 'gpu'
    env = EnvironmentDef(
        resources=[
            ResourceDef(name="gpu", capacity=4),
            ResourceDef(name="cpu", capacity=8),  # Unused resource
        ]
    )

    # 2. Build
    builder = Builder()
    graph = builder.build(simple_graph_ir, environment=env)

    # 3. Assert Broker/Ledger creation
    # Used resource
    ledger_id = "canonical.resource.ledger.gpu"
    broker_id = "canonical.resource.broker.gpu"
    
    assert ledger_id in graph.nodes
    assert broker_id in graph.nodes
    
    ledger_node = graph.nodes[ledger_id]
    # The Ledger Node holds the DiscreteLedger object, capacity is just 1 (slot for the object)
    assert ledger_node.capacity == 1 
    assert ledger_node.initial_tokens == 1
    # Check the payload of the initial token
    initial_ledger = ledger_node.initial_payload
    assert initial_ledger.total == 4
    assert initial_ledger.available == 4

    # Unused resource
    cpu_ledger_id = "canonical.resource.ledger.cpu"
    assert cpu_ledger_id in graph.nodes
    cpu_ledger = graph.nodes[cpu_ledger_id].initial_payload
    assert cpu_ledger.total == 8
~~~~~

#### Acts 2: 修复集成测试

这是大手术。我们需要引入所有的 IC 函数并映射它们。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    # The WorkerNode receives a single token on its 'worker_input' port.
    # The payload of this token is the dictionary of actual arguments.
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload

    # Simulate work based on the unpacked payload
    val = worker_payload["x"]  # The payload is the raw value, not another Token
    return {"worker_result": Token(payload=val + 1)}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    # We will set the global GPU resource to have initial_tokens = 1.
    # This should force them to run sequentially.

    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp
    )

    node_1 = NodeIR(
        id="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        id="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    # Verify D_res exists and was configured by the environment
    assert "canonical.resource.gpu" in physical_graph.nodes
    d_res = physical_graph.nodes["canonical.resource.gpu"]
    assert d_res.initial_tokens == 1

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    # No more partial binding or expected_args needed!
    # The instructions now inspect the Node's port definitions directly.

    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        # We don't map observers here to keep it simple,
        # but in real code we would need to or Reactor will fail if it tries to fire them.
        # Actually, Reactor only fires nodes that are ready.
        # Observers need D_life input. We haven't wired D_life inputs in this test setup manually,
        # but Builder did. D_life starts empty. So Observers won't fire unless D_life gets tokens.
        # Wait, D_life gets tokens from Bleacher/Stainer. So Observers WILL become ready.
        # We must map them to a no-op or mock.
        elif "observability" in node_id:  # Not a func node
            pass

    # We need to handle the global D_life observability sidecar if we want full correctness.
    # Builder created 'global_d_life'.

    # 4. (Deleted) Manual DataNode creation is no longer needed.
    # The Builder now automatically creates 'const_node_1_x' and 'const_node_2_x'
    # based on the literals in NodeIR.inputs.

    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    # This should fill:
    # - global_res_gpu (1 token, payload=None)
    # - const_node_1_x (1 token, payload=10)
    # - const_node_2_x (1 token, payload=20)
    reactor.prime()

    assert memory.get_count("canonical.resource.gpu") == 1
    assert memory.get_count("const.node_1.x") == 1
    assert memory.get_count("const.node_2.x") == 1

    # Verify payloads
    t1 = memory.take("const.node_1.x")
    assert t1.payload == 10
    memory.put(physical_graph.nodes["const.node_1.x"], t1)  # Put it back for execution

    t2 = memory.take("const.node_2.x")
    assert t2.payload == 20
    memory.put(physical_graph.nodes["const.node_2.x"], t2)  # Put it back

    # 7. Step Execution
    async def wait_idle():
        import asyncio

        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    await wait_idle()

    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("canonical.resource.gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()
    await wait_idle()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()
    await wait_idle()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    await wait_idle()

    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await wait_idle()

    await reactor.step()  # Stainer
    await wait_idle()

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~
~~~~~python.new
import pytest
from typing import Dict

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.reactor import Reactor
# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_broker
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}

def noop_observer(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    return {}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp
    )

    node_1 = NodeIR(
        id="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        id="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "broker" in node_id:
            func_map[node_id] = discrete_broker
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        elif "observability" in node_id:
            func_map[node_id] = noop_observer

    # 5. Initialize Reactor
    reactor = Reactor(physical_graph, memory, executor, func_map)

    # 6. Prime the reactor.
    reactor.prime()
    
    # Assert initial state of Ledger
    ledger_node_id = "canonical.resource.ledger.gpu"
    assert memory.get_count(ledger_node_id) == 1
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))

    # 7. Step Execution Logic
    async def wait_idle():
        import asyncio
        while reactor.active_task_count > 0:
            await asyncio.sleep(0.001)

    # --- SIMULATION ---
    # The new graph has many more steps due to Probe -> Req -> Broker -> Bleacher
    
    # Round 1: Probes fire (providing Amount and X)
    await reactor.step() 
    await wait_idle()
    
    # Round 2: Requestors fire (sending Req Tokens to Buffer)
    await reactor.step()
    await wait_idle()
    
    # Check Buffer state
    req_buffer_id = "buffer.req.gpu"
    assert memory.get_count(req_buffer_id) == 2  # Both requests are in buffer

    # Round 3: Broker fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    await reactor.step()
    await wait_idle()
    
    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
    
    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4: 
    # - The lucky Bleacher (who got GNT) fires.
    # - The Broker attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1). 
    #   Logic: 0 < 1. Reject & Recirculate.
    
    fired = await reactor.step()
    await wait_idle()
    
    # If Broker fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.
    
    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer
    
    # We loop until resource is released (Ledger becomes 1)
    max_steps = 20
    for _ in range(max_steps):
        await reactor.step()
        await wait_idle()
        
        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break
            
    assert ledger.available == 1
    
    # Now the second task can proceed.
    # Broker fires -> Grants -> Bleacher -> Worker -> Stainer
    for _ in range(10):
        if memory.get_count(req_buffer_id) == 0 and memory.get_count("buffer.rel.gpu") == 0:
             # If buffers are empty and tasks done, we are good.
             pass
        await reactor.step()
        await wait_idle()

    # Final check: Ledger full, Buffers empty
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 1
    assert memory.get_count(req_buffer_id) == 0
~~~~~

### 下一步建议
测试通过后，我们的物理层就真正具备了“智能”的资源管理能力。
接下来的步骤可能是优化 Reactor 的调度效率，或者增强 Broker 的公平性（目前 FIFO 取决于 Python Dict 顺序和 Buffer 实现）。
但首先，我们需要确认本次重构没有引入回归。
