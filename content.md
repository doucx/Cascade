简要回答：
好的，进入阶段 5.2。我们将定义 `EmitterNode` 的 Spec，并创建一个“黑洞测试”——验证在当前没有实现发射逻辑的情况下，即使图运行结束，我们也无法从外部获取结果。

## [WIP] test(vm): Create Phase 5.2 Emission tests and spec

### 用户需求
1.  在 `cascade-spec` 中定义 `PhysicsEmitterNode` (静态拓扑) 和 `EmitterNode` (运行时物理)。
2.  创建 `tests/reactor/test_result_emission.py`，测试 Reactor 的数据发射能力。
3.  测试应展示如何注册外部 Sink，以及 EmitterNode 如何引用该 Sink。

### 评论
这是全对称架构的输出端。`EmitterNode` 是连接“图内物理世界”与“图外宿主环境”的桥梁。API 设计上，我们采用 `sink_id` 引用机制，保持图的可序列化性，将副作用（回调/Future）留在 Reactor 的运行时注册表中。

### 目标
1.  修改 `packages/cascade-spec/src/cascade/spec/topology.py`。
2.  修改 `packages/cascade-spec/src/cascade/spec/physics.py`。
3.  创建 `packages/cascade-vm/tests/reactor/test_result_emission.py` (RED)。

### 基本原理
-   **API 设计**: `EmitterNode` 携带一个 `sink_id` 字符串。Reactor 提供 `register_sink(sink_id, callback)` 方法。
-   **测试预期**: 测试将构建一个包含 `EmitterNode` 的图，注册一个 `asyncio.Future` 作为 Sink，并运行 Reactor。在 RED 阶段，由于 Reactor 忽略 `EmitterNode`，Future 将永远不会被设置，导致测试超时失败。

### 标签
#intent/tooling #flow/draft #priority/high #comp/spec #comp/tests #concept/io #task/domain/runtime #task/object/emitter #task/action/test #task/state/continue

---

### Script

#### Acts 1: 定义 Emitter Spec

在静态拓扑和运行时物理层中定义 Emitter 节点。

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
class ChannelDef:
~~~~~
~~~~~python.new
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
    """
    A specialized node that projects internal tokens to the external world.
    It acts as a boundary bridge.
    """
    current_node_instance_hash: str
    name: str
    sink_id: str  # Identifier for the external sink (e.g. "client_response")
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelDef:
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
~~~~~
~~~~~python.new
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)
    # Special lifecycle nodes
    terminator_nodes: Dict[str, PhysicsTerminatorNode] = field(default_factory=dict)
    emitter_nodes: Dict[str, PhysicsEmitterNode] = field(default_factory=dict)
~~~~~

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
~~~~~
~~~~~python.new
class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    pass


class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """
    def __init__(
        self, 
        name: str, 
        sink_id: str,
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, resource_requirements)
        self.sink_id = sink_id
~~~~~

#### Acts 2: 创建黑洞测试

创建一个测试，验证在没有实现 Emitter 逻辑时，数据无法传出。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_result_emission.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated
from cascade.runtime.resource_manager import ResourceManager

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink():
    """
    Verifies that an EmitterNode correctly pushes data to a registered external sink.
    
    Topology: DataNode -> EmitterNode -> TerminatorNode
    
    Flow:
    1. Inject token "Hello World" into DataNode.
    2. EmitterNode picks it up and (should) push to sink.
    3. TerminatorNode picks it up (via shared input or sequence) and stops reactor.
    
    For simplicity in this unit test, we wire:
    DataNode -> EmitterNode
             -> TerminatorNode (Parallel consumption or just separate trigger)
             
    Actually, to ensure we capture the emission BEFORE termination, 
    we should probably chain them if possible, or just rely on the Reactor processing 
    events in order. 
    
    Let's use a shared DataNode for simplicity. Both Emitter and Terminator listen to it.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Topology
    d_in = DataNode(name="result_slot")
    
    # Emitter: Sends data to "main_output"
    emitter = EmitterNode(name="emit", sink_id="main_output", resource_requirements={"slots": 1})
    emitter.add_input(Port(name="data", source=d_in))
    
    # Terminator: Stops the reactor
    terminator = TerminatorNode(name="term", resource_requirements={"slots": 1})
    terminator.add_input(Port(name="signal", source=d_in))
    
    reactor.register_node(d_in)
    reactor.register_node(emitter)
    reactor.register_node(terminator)
    
    # 2. Register Sink
    # API Requirement: Reactor must support sink registration
    result_future = asyncio.Future()
    
    # NOTE: This method does not exist yet (RED)
    if hasattr(reactor, "register_sink"):
        reactor.register_sink("main_output", result_future.set_result)
    else:
        # If API is missing, we fail fast, but for TDD strictness we might want to 
        # allow the code to run and fail on the result not being set.
        # But we need to call the API to define it.
        # Let's assume we implement it in the next step.
        # For now, we simulate the API call failure or just skip if we want "RuntimeError".
        # But to be clean, let's call it and expect AttributeError if not implemented.
        try:
            reactor.register_sink("main_output", result_future.set_result)
        except AttributeError:
            pytest.fail("Reactor.register_sink API is missing")

    # 3. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 4. Inject Result
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 5. Wait for completion
    try:
        # Wait for reactor to stop (triggered by Terminator)
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        await run_task
        # If it timed out, it means Terminator didn't fire, which is a separate issue 
        # (or resource contention). But here we assume Terminator works (Phase 5.1).
    
    # 6. Verify Result
    # This is the core assertion. Did the sink receive the data?
    try:
        result = result_future.result()
        assert result == "Hello World"
    except asyncio.InvalidStateError:
        pytest.fail("Sink was never called with the result")
~~~~~

### 下一步建议
测试现在会失败（`AttributeError: 'Reactor' object has no attribute 'register_sink'` 或 Sink 未被调用）。
下一步（阶段 5.2.2）我们将：
1.  在 `Reactor` 中实现 `register_sink` 方法。
2.  在 `Reactor._fire` 中添加对 `EmitterNode` 的处理逻辑。
3.  确保测试变绿。
