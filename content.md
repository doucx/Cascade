这是 Phase 2 的实施计划。本计划不仅实现了 `Builder` 对 `Assembly` 的支持，还顺带解决了一个关键的命名一致性问题（`current` vs `canonical` 哈希），确保了系统符合“哈希强制长命名规范”。

## [WIP] feat: 升级 Builder 以产出 Assembly 并统一规范哈希命名

### 用户需求

1.  **统一哈希命名**: 将 `ReflectionAnalyzer` 和 `HashingService` 中的 `current_code_structure_hash` 更正为 `canonical_code_structure_hash`，以符合架构公理和路线图要求。
2.  **增强 Expander**: 修改 `SubGraph` 结构，使其显式暴露 `worker` 节点，方便 `Builder` 访问。
3.  **改造 Builder**: 修改 `Builder.build` 方法，使其返回包含 `BipartiteGraph` 和 `SymbolTable` 的 `Assembly` 对象。
4.  **填充符号表**: 在构建过程中，将 Worker 节点的物理 ID 与其 `canonical_code_structure_hash` 的映射写入 `Assembly.symbol_table`。
5.  **适配下游**: 更新 `VMExecutionStrategy` 和相关测试，以适应 `Builder` 返回值的变化。

### 评论

这是一个涉及多组件的协同变更。通过这次修改，我们将正式确立编译器与运行时之间的“程序集（Assembly）契约”。虽然 `VMExecutionStrategy` 的完整链接逻辑重构留待 Phase 3，但本计划确保了编译器的产出物已经就绪，并且修复了底层的命名债。

### 目标

1.  重构 `cascade-reflection`，统一使用 `canonical_code_structure_hash`。
2.  重构 `cascade-compiler` 的 `Expander`，暴露 `worker` 节点。
3.  升级 `cascade-compiler` 的 `Builder`，产出 `Assembly`。
4.  修复 `cascade-engine` 和所有受影响的测试用例。

### 基本原理

*   **哈希一致性**: 路线图明确指出 `SymbolTable` 映射的是 `Canonical Hash`。代码库中混用 `current` 是不准确的，必须在生成 `Assembly` 之前修正。
*   **Expander 增强**: `Builder` 需要知道哪个节点是 Worker 才能建立映射。与其在 `Builder` 中根据 ID 规则猜测，不如让 `Expander`（它创建了节点）显式返回这一信息。
*   **兼容性维持**: 虽然 Engine 的逻辑还没完全跟上，但我们需要做最小限度的适配（unpack assembly），以保证 CI/CD 不会中断。

### 标签

#intent/build #flow/draft #priority/high
#comp/compiler #comp/runtime #comp/reflection #concept/linker
#scope/core
#task/domain/compiler #task/object/assembly #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 统一哈希命名 (Reflection)

将 `ReflectionAnalyzer` 生成的哈希键名和 `HashingService` 使用的键名从 `current_code_structure_hash` 更正为 `canonical_code_structure_hash`。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/analyzer.py
~~~~~
~~~~~python.old
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        current_code_structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = current_code_structure_hash

        return TaskDef(
~~~~~
~~~~~python.new
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        canonical_code_structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["canonical_code_structure_hash"] = canonical_code_structure_hash

        return TaskDef(
~~~~~

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Node],
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        current_code_structure_hash = definition.fingerprint[
            "current_code_structure_hash"
        ]
        components = [f"CodeHash:{current_code_structure_hash}"]

        # 2. Purity Salt
~~~~~
~~~~~python.new
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Node],
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        canonical_code_structure_hash = definition.fingerprint[
            "canonical_code_structure_hash"
        ]
        components = [f"CodeHash:{canonical_code_structure_hash}"]

        # 2. Purity Salt
~~~~~

#### Acts 2: 增强 Expander (Compiler)

修改 `SubGraph` 定义以包含 `worker` 字段，并在 `Expander.expand_node` 中填充它。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: Optional[BleachNode] = None
    stainer: Optional[StainNode] = None


class Expander:
~~~~~
~~~~~python.new
@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None


class Expander:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
        subgraph.stainer = f_post

        # 3. Create Internal Wiring (Channels)
~~~~~
~~~~~python.new
        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
        subgraph.worker = f_worker
        subgraph.stainer = f_post

        # 3. Create Internal Wiring (Channels)
~~~~~

#### Acts 3: 升级 Builder (Compiler)

修改 `Builder.build` 以构建 `Assembly` 并填充符号表。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from typing import List

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from .expander import Expander
from .validator import GraphValidator
~~~~~
~~~~~python.new
from typing import List

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph
from cascade.spec.environment import EnvironmentDef
from cascade.spec.assembly import Assembly
from .expander import Expander
from .validator import GraphValidator
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )

        # 2. Phase 0: Setup Global Infrastructure
        for policy in self._policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Expand and Wire Nodes
        for node_ir in graph_ir.nodes:
            # 3.1 Expand triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.current_node_instance_hash, subgraph)

            # 3.2 Apply wiring policies
            for policy in self._policies:
                policy.apply(ctx, node_ir, subgraph)

        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        return physical_graph
~~~~~
~~~~~python.new
    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> Assembly:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )
        symbol_table = {}

        # 2. Phase 0: Setup Global Infrastructure
        for policy in self._policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Expand and Wire Nodes
        for node_ir in graph_ir.nodes:
            # 3.1 Expand triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.current_node_instance_hash, subgraph)

            # 3.1.b Populate Symbol Table
            # Map the physical worker ID to the canonical code structure hash
            if subgraph.worker:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.worker.id] = canonical_hash

            # 3.2 Apply wiring policies
            for policy in self._policies:
                policy.apply(ctx, node_ir, subgraph)

        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        return Assembly(
            graph=physical_graph,
            symbol_table=symbol_table,
            metadata={"compiler": "cascade-compiler-v0.1.0"},
        )
~~~~~

#### Acts 4: 适配 Engine

修改 `VMExecutionStrategy` 以解包 `Assembly`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        compiler = IRGenerator()
        graph_ir = compiler.generate(target)
        
        builder = Builder()
        physical_graph = builder.build(graph_ir, env_def)

        # 2. Runtime Setup
        # ----------------
~~~~~
~~~~~python.new
        compiler = IRGenerator()
        graph_ir = compiler.generate(target)
        
        builder = Builder()
        assembly = builder.build(graph_ir, env_def)
        physical_graph = assembly.graph

        # 2. Runtime Setup
        # ----------------
~~~~~

#### Acts 5: 适配及修复测试

修改测试用例以适应 `canonical_code_structure_hash` 和 `Assembly` 返回值。

**5.1. 修复 Frontend Generator 测试**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "add"
    assert node_ir.task.name == "add"
    assert "current_code_structure_hash" in node_ir.task.fingerprint

    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.inputs == {"0": 1, "1": 2}
~~~~~
~~~~~python.new
    node_ir = graph_ir.nodes[0]
    assert node_ir.name == "add"
    assert node_ir.task.name == "add"
    assert "canonical_code_structure_hash" in node_ir.task.fingerprint

    # Verify that positional arguments are correctly mapped to string keys
    assert node_ir.inputs == {"0": 1, "1": 2}
~~~~~

**5.2. 修复 Backend Builder 测试**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    graph = builder.build(sample_graph_ir, environment=EnvironmentDef())

    # Assert nodes: 2 triads (6*2=12) + 1 D_life + 1 F_obs + 1 D_dep + 1 D_pulse = 16 nodes
    assert len(graph.nodes) == 16
    assert "global.observability.bus" in graph.nodes
~~~~~
~~~~~python.new
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    assembly = builder.build(sample_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph
    symbol_table = assembly.symbol_table

    # Assert Symbol Table
    # worker nodes should be in symbol table
    assert "node_a.worker" in symbol_table
    assert symbol_table["node_a.worker"] == "abc"
    assert "node_b.worker" in symbol_table
    assert symbol_table["node_b.worker"] == "abc"

    # Assert nodes: 2 triads (6*2=12) + 1 D_life + 1 F_obs + 1 D_dep + 1 D_pulse = 16 nodes
    assert len(graph.nodes) == 16
    assert "global.observability.bus" in graph.nodes
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    graph = builder.build(source_only_graph_ir, environment=EnvironmentDef())

    # 1. Assert Pulse node creation
    pulse_id = PhysicalIdGenerator.pulse_source("source_node")
~~~~~
~~~~~python.new
def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    assembly = builder.build(source_only_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph

    # 1. Assert Pulse node creation
    pulse_id = PhysicalIdGenerator.pulse_source("source_node")
~~~~~

**5.3. 修复其他受影响的集成测试**

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python.old
    # 2. Build
    builder = Builder()
    graph = builder.build(simple_graph_ir, environment=env)

    # 3. Assert Broker/Ledger creation
~~~~~
~~~~~python.new
    # 2. Build
    builder = Builder()
    assembly = builder.build(simple_graph_ir, environment=env)
    graph = assembly.graph

    # 3. Assert Broker/Ledger creation
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
~~~~~
~~~~~python.old
def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    graph = builder.build(empty_graph_ir, environment=EnvironmentDef())

    # 1. Assert D_life exists (Baseline check)
~~~~~
~~~~~python.new
def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    assembly = builder.build(empty_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph

    # 1. Assert D_life exists (Baseline check)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    physical_graph = builder.build(graph_ir, environment)

    # 3. The Purity Test: Attempt to serialize the graph
    try:
        serialized_graph = pickle.dumps(physical_graph)
        # Optional: check that it can be deserialized correctly
        deserialized_graph = pickle.loads(serialized_graph)
    except Exception as e:
~~~~~
~~~~~python.new
    graph_ir = generator.generate(workflow)
    assembly = builder.build(graph_ir, environment)
    physical_graph = assembly.graph

    # 3. The Purity Test: Attempt to serialize the graph
    try:
        serialized_graph = pickle.dumps(physical_graph)
        # Optional: check that it can be deserialized correctly
        deserialized_graph = pickle.loads(serialized_graph)
    except Exception as e:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # 2. Build Physical Graph
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    physical_graph = builder.build(graph_ir, env)

    # --- PART A: TOPOLOGY ASSERTION ---
~~~~~
~~~~~python.new
    # 2. Build Physical Graph
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    assembly = builder.build(graph_ir, env)
    physical_graph = assembly.graph

    # --- PART A: TOPOLOGY ASSERTION ---
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, env)
    inspector = GraphInspector(physical_graph)
~~~~~
~~~~~python.new
    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    assembly = builder.build(graph_ir, env)
    physical_graph = assembly.graph
    inspector = GraphInspector(physical_graph)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~
~~~~~python.old
    # 2. Build Physical Graph
    builder = Builder()
    physical_graph = builder.build(graph_ir, EnvironmentDef())

    # 3. Inspect Topology
~~~~~
~~~~~python.new
    # 2. Build Physical Graph
    builder = Builder()
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 3. Inspect Topology
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
    assert bleacher.id == "node_1.bleach"
    assert stainer.id == "node_1.stain"

    # Check intermediate nodes
    worker = subgraph.nodes["node_1.worker"]
    assert isinstance(worker, WorkerNode)

    d_trace = subgraph.nodes["node_1.data.trace"]
~~~~~
~~~~~python.new
    assert bleacher.id == "node_1.bleach"
    assert stainer.id == "node_1.stain"

    # Check intermediate nodes
    worker = subgraph.worker
    assert isinstance(worker, WorkerNode)
    assert worker.id == "node_1.worker"

    d_trace = subgraph.nodes["node_1.data.trace"]
~~~~~

### 下一步建议

完成 Phase 2 后，我们将进入 **Phase 3: 运行时层**。
我们需要实现 `CodeRegistry`，并在 `VMExecutionStrategy` 中实现真正的链接逻辑（使用 `Assembly.symbol_table` 而不是当前的 hack）。这涉及到重构 `Linker` 和 Registry。
