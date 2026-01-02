## [WIP] refactor(compiler): 引入 PhysicalIdGenerator 以规范化物理节点命名

### 用户需求
1.  **消除硬编码**: 将 `expander.py` 和 `builder.py` 中用于生成物理节点 ID 的魔法字符串（如 `_bleach`, `_stain`, `global_res_`）替换为基于 `Fingerprint` 或标准化前缀的确定性命名。
2.  **符合公理**: 确保所有物理节点的 ID 符合 `[State]_[Source]_[Object]_hash` 的架构公理，或至少使用语义明确的长命名空间（对于全局资源）。

### 评论
命名即架构。当前的 ID 生成逻辑过于随意，导致系统难以在分布式环境或持久化存储中唯一锚定物理实体。通过引入 `PhysicalIdGenerator`，我们将 ID 生成逻辑集中化、规范化，使其成为系统的“命名当局”。这不仅是代码整洁的问题，更是为了确保系统在未来的分布式演进中拥有稳固的身份基础。

### 目标
1.  在 `cascade-compiler` 中创建一个新的辅助模块 `cascade.compiler.utils.naming`，包含 `PhysicalIdGenerator` 类。
2.  实现该生成器，支持生成三连体节点 ID、资源节点 ID、常量节点 ID 和观测总线 ID。
3.  重构 `Expander` 和 `Builder`，使用该生成器替代硬编码字符串。
4.  更新所有受影响的测试用例（`test_builder.py`, `test_expander.py`, `test_resource_backpressure.py`）。

### 基本原理
我们将采用一种分层命名策略，所有 ID 都应视为不透明的标识符，由生成器统一管理：
*   **任务衍生节点**: 使用 `<task_node_id>.<suffix>` 的形式（例如 `[hash].bleach`）。
*   **全局资源**: 使用 `canonical.resource.<name>`。这明确了其作为全局、规范实体的身份。
*   **字面量常量**: 使用 `const.<target_node_id>.<arg_name>`。
*   **观测系统**: 使用 `global.observability.bus` 和 `global.observability.observer`。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #concept/identity #scope/core #ai/instruct #task/domain/compiler #task/object/physical-id #task/action/canonicalize-naming #task/state/continue

---

### Script

#### Acts 1: 创建 PhysicalIdGenerator

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-compiler/src/cascade/compiler/utils
touch packages/cascade-compiler/src/cascade/compiler/utils/__init__.py
~~~~~

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
~~~~~
~~~~~python
class PhysicalIdGenerator:
    """
    The central authority for generating canonical IDs for physical nodes.
    Ensures consistency and adherence to naming axioms across the compiler.
    """

    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.bleach"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.worker"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.stain"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.in"

    @staticmethod
    def worker_out_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.out"

    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
    def global_resource(resource_name: str) -> str:
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        return f"const.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return "global.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"
~~~~~

#### Acts 2: 重构 Expander

修改 `Expander` 以使用 `PhysicalIdGenerator`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
~~~~~
~~~~~python.new
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.compiler.utils.naming import PhysicalIdGenerator


@dataclass
class SubGraph:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.id

        f_pre_id = f"{base_id}_bleach"
        d_worker_in_id = f"{base_id}_worker_in"
        f_worker_id = f"{base_id}_worker"
        d_worker_out_id = f"{base_id}_worker_out"
        d_trace_id = f"{base_id}_trace"
        f_post_id = f"{base_id}_stain"

        # 2. Create Nodes
~~~~~
~~~~~python.new
        # 1. Generate IDs for all physical entities
        # We use the logical node ID as a prefix to ensure uniqueness.
        base_id = node_ir.id

        f_pre_id = PhysicalIdGenerator.bleach_node(base_id)
        d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
        f_worker_id = PhysicalIdGenerator.worker_node(base_id)
        d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
        d_trace_id = PhysicalIdGenerator.trace_data(base_id)
        f_post_id = PhysicalIdGenerator.stain_node(base_id)

        # 2. Create Nodes
~~~~~

#### Acts 3: 重构 Builder

修改 `Builder` 以使用 `PhysicalIdGenerator`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.environment import EnvironmentDef
from .expander import Expander, SubGraph


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = f"global_res_{res_def.name}"
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = "global_d_life"
        f_obs_id = "global_f_obs"

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
~~~~~
~~~~~python.new
from cascade.spec.environment import EnvironmentDef
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = PhysicalIdGenerator.global_resource(res_def.name)
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # Case B: Literal Value (Constant)
                else:
                    # Create a dedicated DataNode for this constant
                    # Naming convention: const_[target_node]_[arg_name]
                    const_node_id = f"const_{node_ir.id}_{arg_name}"
                    const_node = PhysicsDataNode(
                        id=const_node_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
~~~~~
~~~~~python.new
                # Case B: Literal Value (Constant)
                else:
                    # Create a dedicated DataNode for this constant
                    const_node_id = PhysicalIdGenerator.constant(
                        node_ir.id, arg_name
                    )
                    const_node = PhysicsDataNode(
                        id=const_node_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name in node_ir.constraints:
                res_node_id = f"global_res_{res_name}"
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
~~~~~
~~~~~python.new
        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name in node_ir.constraints:
                res_node_id = PhysicalIdGenerator.global_resource(res_name)
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
~~~~~

#### Acts 4: 更新测试用例

**更新 `test_builder.py`**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs = 14 nodes
    assert len(graph.nodes) == 14
    assert "global_d_life" in graph.nodes
    assert "global_f_obs" in graph.nodes
    assert "node_a_stain" in graph.nodes
    assert "node_b_bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
~~~~~
~~~~~python.new
    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs = 14 nodes
    assert len(graph.nodes) == 14
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.stain" in graph.nodes
    assert "node_b.bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    # 1. Test data dependency wiring
    data_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a_stain" and c.target_node_id == "node_b_bleach"
    )
    assert data_channel is not None
    assert data_channel.source_port == "output"

    # 2. Test observability wiring
    d_life_id = "global_d_life"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a_bleach" in source_ids
    assert "node_a_stain" in source_ids
    assert "node_b_bleach" in source_ids
    assert "node_b_stain" in source_ids
~~~~~
~~~~~python.new
    # 1. Test data dependency wiring
    data_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.stain" and c.target_node_id == "node_b.bleach"
    )
    assert data_channel is not None
    assert data_channel.source_port == "output"

    # 2. Test observability wiring
    d_life_id = "global.observability.bus"
    obs_channels = [c for c in graph.channels if c.target_node_id == d_life_id]

    assert len(obs_channels) == 4  # 2 starts, 2 ends

    source_ids = {c.source_node_id for c in obs_channels}
    assert "node_a.bleach" in source_ids
    assert "node_a.stain" in source_ids
    assert "node_b.bleach" in source_ids
    assert "node_b.stain" in source_ids
~~~~~

**更新 `test_builder_environment.py`**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python.old
    # 3. Assert D_res creation
    # Used resource should exist
    assert "global_res_gpu" in graph.nodes
    gpu_node = graph.nodes["global_res_gpu"]
    assert gpu_node.capacity == 4
    # Initial tokens should match capacity (potential energy)
    assert gpu_node.initial_tokens == 4

    # Unused resource should ALSO exist (Physics is objective)
    assert "global_res_cpu" in graph.nodes
    cpu_node = graph.nodes["global_res_cpu"]
    assert cpu_node.capacity == 8
~~~~~
~~~~~python.new
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

**更新 `test_builder_observability.py`**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
~~~~~
~~~~~python.old
def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    graph = builder.build(empty_graph_ir, environment=EnvironmentDef())

    # 1. Assert D_life exists (Baseline check)
    assert "global_d_life" in graph.nodes

    # 2. Assert F_obs exists (New Requirement)
    f_obs_id = "global_f_obs"
    assert f_obs_id in graph.nodes
    f_obs = graph.nodes[f_obs_id]
    assert isinstance(f_obs, ObservabilityNode)

    # 3. Assert Connection: D_life -> F_obs
    obs_channels = [
        c
        for c in graph.channels
        if c.source_node_id == "global_d_life" and c.target_node_id == f_obs_id
    ]
    assert len(obs_channels) == 1
    channel = obs_channels[0]
~~~~~
~~~~~python.new
def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    graph = builder.build(empty_graph_ir, environment=EnvironmentDef())

    # 1. Assert D_life exists (Baseline check)
    assert "global.observability.bus" in graph.nodes

    # 2. Assert F_obs exists (New Requirement)
    f_obs_id = "global.observability.observer"
    assert f_obs_id in graph.nodes
    f_obs = graph.nodes[f_obs_id]
    assert isinstance(f_obs, ObservabilityNode)

    # 3. Assert Connection: D_life -> F_obs
    obs_channels = [
        c
        for c in graph.channels
        if c.source_node_id == "global.observability.bus" and c.target_node_id == f_obs_id
    ]
    assert len(obs_channels) == 1
    channel = obs_channels[0]
~~~~~

**更新 `test_expander.py`**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
    bleacher = subgraph.bleacher
    stainer = subgraph.stainer

    assert isinstance(bleacher, BleachNode)
    assert isinstance(stainer, StainNode)
    assert bleacher.id == "node_1_bleach"
    assert stainer.id == "node_1_stain"

    # Check intermediate nodes
    worker = subgraph.nodes["node_1_worker"]
    assert isinstance(worker, WorkerNode)

    d_trace = subgraph.nodes["node_1_trace"]
    assert isinstance(d_trace, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 6 internal channels
~~~~~
~~~~~python.new
    bleacher = subgraph.bleacher
    stainer = subgraph.stainer

    assert isinstance(bleacher, BleachNode)
    assert isinstance(stainer, StainNode)
    assert bleacher.id == "node_1.bleach"
    assert stainer.id == "node_1.stain"

    # Check intermediate nodes
    worker = subgraph.nodes["node_1.worker"]
    assert isinstance(worker, WorkerNode)

    d_trace = subgraph.nodes["node_1.data.trace"]
    assert isinstance(d_trace, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 6 internal channels
~~~~~

**更新 `test_resource_backpressure.py`**

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # Verify D_res exists and was configured by the environment
    assert "global_res_gpu" in physical_graph.nodes
    d_res = physical_graph.nodes["global_res_gpu"]
    assert d_res.initial_tokens == 1

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    # Note: We must bind expected_args for bleacher so it knows 'x' is data, 'res_gpu' is resource
    bleacher_fn = partial(standard_bleacher, expected_args=["x"])

    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith("_bleach"):
            func_map[node_id] = bleacher_fn
        elif node_id.endswith("_stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith("_worker"):
            func_map[node_id] = mock_worker
        # We don't map observers here to keep it simple,
        # but in real code we would need to or Reactor will fail if it tries to fire them.
        # Actually, Reactor only fires nodes that are ready.
        # Observers need D_life input. We haven't wired D_life inputs in this test setup manually,
        # but Builder did. D_life starts empty. So Observers won't fire unless D_life gets tokens.
        # Wait, D_life gets tokens from Bleacher/Stainer. So Observers WILL become ready.
        # We must map them to a no-op or mock.
        elif "d_life" in node_id:  # Not a func node
            pass

    # We need to handle the global D_life observability sidecar if we want full correctness.
~~~~~
~~~~~python.new
    # Verify D_res exists and was configured by the environment
    assert "canonical.resource.gpu" in physical_graph.nodes
    d_res = physical_graph.nodes["canonical.resource.gpu"]
    assert d_res.initial_tokens == 1

    # 3. Setup VM
    memory = VolatileMemory()
    executor = PhysicsExecutor()

    # Map functions
    # Note: We must bind expected_args for bleacher so it knows 'x' is data, 'res_gpu' is resource
    bleacher_fn = partial(standard_bleacher, expected_args=["x"])

    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = bleacher_fn
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
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # - global_res_gpu (1 token, payload=None)
    # - const_node_1_x (1 token, payload=10)
    # - const_node_2_x (1 token, payload=20)
    reactor.prime()
    
    assert memory.get_count("global_res_gpu") == 1
    assert memory.get_count("const_node_1_x") == 1
    assert memory.get_count("const_node_2_x") == 1
    
    # Verify payloads
    t1 = memory.take("const_node_1_x")
    assert t1.payload == 10
    memory.put(physical_graph.nodes["const_node_1_x"], t1) # Put it back for execution

    t2 = memory.take("const_node_2_x")
    assert t2.payload == 20
    memory.put(physical_graph.nodes["const_node_2_x"], t2) # Put it back

    # 7. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("global_res_gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()

    assert memory.get_count("global_res_gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("global_res_gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await reactor.step()  # Stainer

    assert memory.get_count("global_res_gpu") == 1
~~~~~
~~~~~python.new
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
    memory.put(physical_graph.nodes["const.node_1.x"], t1) # Put it back for execution

    t2 = memory.take("const.node_2.x")
    assert t2.payload == 20
    memory.put(physical_graph.nodes["const.node_2.x"], t2) # Put it back
    
    # 7. Step Execution
    # Step 1: Both Bleachers are ready on 'x', but contend for 'res_gpu'.
    # With the new atomic Reactor, only ONE should fire.
    fired = await reactor.step()
    # What fires?
    # 1. Bleacher (consumes 1 GPU, 1 X) -> fires.
    # The other Bleacher cannot fire because D_res is empty.

    assert fired == 1
    assert memory.get_count("canonical.resource.gpu") == 0  # Resource taken

    # Step 2: The fired Triad proceeds.
    # Worker fires.
    await reactor.step()

    # Step 3: Stainer fires.
    # This should return the resource.
    await reactor.step()

    assert memory.get_count("canonical.resource.gpu") == 1  # Resource returned!

    # Step 4: Now the second Bleacher can fire.
    fired_2 = await reactor.step()
    assert fired_2 == 1
    assert memory.get_count("canonical.resource.gpu") == 0

    # Step 5 & 6: Finish second task
    await reactor.step()  # Worker
    await reactor.step()  # Stainer

    assert memory.get_count("canonical.resource.gpu") == 1
~~~~~

### 下一步建议
我们已经完成了命名规范化。至此，阶段四的核心问题（观测死锁、字面量缺失、命名混乱）已基本解决。

作为本宏观任务的收尾，建议运行完整的测试套件，确保没有回归，然后提交所有更改。
