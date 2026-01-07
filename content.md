根据你的路线图，我将生成执行 **Phase 3.1: 编译器增强** 的计划。此计划将引入 `CompilationManifest` 和 `CompilationArtifact`，并更新编译器前端和后端以生成和填充这些结构，同时修复因破坏性变更（Breaking Change）导致的所有受影响测试。

这是确定性重构的第一步，为后续消除“猜测性编程”奠定基础。

[简要回答]
我们将执行 Phase 3.1，引入 `CompilationManifest` 和 `CompilationArtifact`，使编译器显式返回逻辑 UUID 到物理节点 ID 的映射。这将涉及修改 Spec、Frontend Generator、Backend Builder 以及所有依赖 `Builder.build` 的测试用例。

## [WIP] feat(compiler): 引入 CompilationManifest 以建立确定的逻辑-物理映射

### 用户需求
目前 `Builder.build()` 仅返回物理 `Assembly`。运行时策略层（Strategy）在拥有逻辑 `LazyResult` 对象时，不得不猜测其对应的物理节点 ID（例如假设 ID 为 `hash` 或 `hash.worker`）。这种隐式假设是脆弱的。
用户需要一个权威的、由编译器生成的清单（Manifest），明确记录逻辑 UUID 与物理节点 ID 之间的映射关系。

### 评论
这是 ADAP 协议（假设驱动分析）的直接应用。通过将映射关系具体化为数据结构，我们消除了运行时对编译器内部命名约定的隐式依赖。

### 目标
1.  在 `cascade-spec` 中定义 `CompilationManifest` 和 `CompilationArtifact`。
2.  更新 `NodeIR` 以携带可选的 `logical_id` (UUID)。
3.  更新 `IRGenerator` 以在生成 IR 时填充 `logical_id`。
4.  更新 `Builder` 以生成 Manifest 并返回 `CompilationArtifact`。
5.  修复所有因 `Builder.build` 返回值类型改变而破坏的单元测试和集成测试。

### 基本原理
-   **SSoT (单一事实来源)**: 编译器是唯一知道逻辑节点如何映射到物理节点的组件。它必须将这一知识显式导出，而不是让下游去重新计算或猜测。
-   **Artifact 封装**: 将 `Assembly`（物理图）和 `Manifest`（元数据）封装在 `CompilationArtifact` 中，为未来增加更多编译产物（如调试符号、Source Map）预留空间。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high
#comp/engine #scope/core
#task/domain/compiler #task/object/compilation-manifest #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 更新 Spec 定义 (NodeIR & Assembly)

首先，我们在 IR 中增加 `logical_id` 字段，并在物理层定义新的 Artifact 结构。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class NodeIR:
    current_node_instance_hash: str

    name: str

    task: TaskDef

    inputs: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class NodeIR:
    current_node_instance_hash: str

    name: str

    task: TaskDef

    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/assembly.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class Assembly:
    # The physical topology, defining nodes (What) and channels (How).
    graph: BipartiteGraph

    # The symbol table, mapping physical node IDs to canonical code structure hashes.
    # Key: Physical Node ID (e.g., "hash123.worker")
    # Value: Canonical Code Structure Hash (e.g., "sha256:abc...")
    symbol_table: SymbolTable = field(default_factory=dict)

    # Metadata about the assembly, such as compiler version, build time, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class Assembly:
    # The physical topology, defining nodes (What) and channels (How).
    graph: BipartiteGraph

    # The symbol table, mapping physical node IDs to canonical code structure hashes.
    # Key: Physical Node ID (e.g., "hash123.worker")
    # Value: Canonical Code Structure Hash (e.g., "sha256:abc...")
    symbol_table: SymbolTable = field(default_factory=dict)

    # Metadata about the assembly, such as compiler version, build time, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompilationManifest:
    # Maps logical UUIDs (from LazyResult) to the base physical node ID.
    # Key: Logical UUID
    # Value: Physical Base ID (current_node_instance_hash)
    logical_to_physical_map: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompilationArtifact:
    assembly: Assembly
    manifest: CompilationManifest
~~~~~

#### Acts 2: 更新编译器前端 (IRGenerator)

更新 `IRGenerator` 以在生成 `NodeIR` 时传递 `logical_id`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
        )
~~~~~
~~~~~python.new
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
        )
~~~~~

#### Acts 3: 更新编译器后端 (Builder)

更新 `Builder` 以生成 `CompilationManifest` 并返回 `CompilationArtifact`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.assembly import Assembly
from .expander import Expander
from .validator import GraphValidator
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.assembly import (
    Assembly,
    CompilationArtifact,
    CompilationManifest,
)
from .expander import Expander
from .validator import GraphValidator
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> Assembly:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
~~~~~
~~~~~python.new
    def build(
        self, graph_ir: GraphIR, environment: EnvironmentDef
    ) -> CompilationArtifact:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        return Assembly(
            graph=physical_graph,
            symbol_table=symbol_table,
            metadata={"compiler": "cascade-compiler-v0.1.0"},
        )
~~~~~
~~~~~python.new
        # 4. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        # 5. Generate Manifest
        logical_to_physical_map = {}
        for node_ir in graph_ir.nodes:
            if node_ir.logical_id:
                logical_to_physical_map[node_ir.logical_id] = (
                    node_ir.current_node_instance_hash
                )

        assembly = Assembly(
            graph=physical_graph,
            symbol_table=symbol_table,
            metadata={"compiler": "cascade-compiler-v0.1.0"},
        )
        manifest = CompilationManifest(logical_to_physical_map=logical_to_physical_map)

        return CompilationArtifact(assembly=assembly, manifest=manifest)
~~~~~

#### Acts 4: 修复单元测试 (Backend)

修复 `tests/unit/backend` 下的所有测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    assembly = builder.build(sample_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph
    symbol_table = assembly.symbol_table
~~~~~
~~~~~python.new
def test_builder_expands_and_wires_nodes(sample_graph_ir):
    builder = Builder()
    artifact = builder.build(sample_graph_ir, environment=EnvironmentDef())
    assembly = artifact.assembly
    graph = assembly.graph
    symbol_table = assembly.symbol_table
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    assembly = builder.build(source_only_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph

    # 1. Assert Pulse node creation
~~~~~
~~~~~python.new
def test_builder_creates_pulse_for_source_node(source_only_graph_ir):
    builder = Builder()
    artifact = builder.build(source_only_graph_ir, environment=EnvironmentDef())
    assembly = artifact.assembly
    graph = assembly.graph

    # 1. Assert Pulse node creation
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python.old
    # 2. Build
    builder = Builder()
    assembly = builder.build(simple_graph_ir, environment=env)
    graph = assembly.graph

    # 3. Assert Broker/Ledger creation
~~~~~
~~~~~python.new
    # 2. Build
    builder = Builder()
    artifact = builder.build(simple_graph_ir, environment=env)
    assembly = artifact.assembly
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
    assembly = builder.build(empty_graph_ir, environment=EnvironmentDef())
    graph = assembly.graph

    # 1. Assert D_life exists (Baseline check)
~~~~~
~~~~~python.new
def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    artifact = builder.build(empty_graph_ir, environment=EnvironmentDef())
    assembly = artifact.assembly
    graph = assembly.graph

    # 1. Assert D_life exists (Baseline check)
~~~~~

#### Acts 5: 修复集成测试 (Integration)

修复 `tests/integration` 下的所有测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_assembly_purity.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    assembly = builder.build(graph_ir, environment)
    assert isinstance(assembly, Assembly)

    # 3. The Purity Test: Attempt to serialize the Assembly
~~~~~
~~~~~python.new
    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
    assembly = artifact.assembly
    assert isinstance(assembly, Assembly)

    # 3. The Purity Test: Attempt to serialize the Assembly
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    assembly = builder.build(graph_ir, environment)
    physical_graph = assembly.graph

    # 3. The Purity Test: Attempt to serialize the graph
~~~~~
~~~~~python.new
    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. The Purity Test: Attempt to serialize the graph
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    assembly = builder.build(graph_ir, env)
    physical_graph = assembly.graph

    # --- PART A: TOPOLOGY ASSERTION ---
~~~~~
~~~~~python.new
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly
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
    assembly = builder.build(graph_ir, env)
    physical_graph = assembly.graph
    inspector = GraphInspector(physical_graph)
~~~~~
~~~~~python.new
    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    artifact = builder.build(graph_ir, env)
    assembly = artifact.assembly
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
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 3. Inspect Topology
~~~~~
~~~~~python.new
    # 2. Build Physical Graph
    builder = Builder()
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. Inspect Topology
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 2. Setup Code Registry for the Compute Service
~~~~~
~~~~~python.new
    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 2. Setup Code Registry for the Compute Service
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 3. Register user code in the CodeRegistry
~~~~~
~~~~~python.new
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. Register user code in the CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    assembly = builder.build(graph_ir, environment=env)
    physical_graph = assembly.graph

    # 3. Setup VM
~~~~~
~~~~~python.new
    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    artifact = builder.build(graph_ir, environment=env)
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. Setup VM
~~~~~

### 下一步建议
我们已经完成了编译器层面的契约增强，并修复了所有受影响的测试。
下一步，我们将执行 **Phase 3.2: 链接器增强**。我们需要在 VM 启动前，利用 Linker 强制验证 Assembly 中的所有代码哈希是否在 Registry 中存在，从而实现“启动前的完整性校验”。这将涉及修改 `Linker` 类并添加新的测试。
