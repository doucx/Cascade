好的，我们开始偿还下一项技术债务：完善 `CompilationManifest`。

当前 `Manifest` 只包含了逻辑 ID 到物理 ID 的映射，缺少了关键的 `entry_points` 和 `exit_points` 信息，这迫使运行时环境去猜测图的入口和出口。我们将通过增强编译器来解决这个问题。

## [WIP] feat(compiler): 完善 CompilationManifest 以包含 entry/exit points

### 用户需求
增强编译器，使其生成的 `CompilationManifest` 包含以下信息：
1.  `entry_points`: 一个列表，包含所有作为图输入源的物理数据节点 ID（例如，常量节点、脉冲节点）。
2.  `exit_points`: 一个字典，将图的最终输出（根 `LazyResult`）的逻辑 UUID 映射到其结果最终所在的物理数据节点 ID。

### 评论
这是一个关键的架构改进，它遵循了“显式优于隐式”的原则。通过让编译器明确声明图的边界，我们消除了运行时环境的猜测工作，使得 `Strategy` 层的实现可以更加健壮和确定。这为未来更复杂的执行策略（如跨进程图执行）铺平了道路。

### 目标
1.  更新 `CompilationManifest` 和 `GraphIR` 的数据结构，以包含新的字段。
2.  增强 `IRGenerator` 以识别并标记根节点。
3.  修改 `ControlFlowWiringPolicy`，为根节点自动创建专用的 `Egress` 数据节点。
4.  更新 `Builder` 以扫描最终的物理图，并从特定模式的节点（`const.*`, `pulse.*`, `egress.*`）中提取信息，填充到 `Manifest` 中。
5.  创建新的集成测试来验证 `Manifest` 内容的正确性。

### 基本原理
1.  **识别根节点**: `IRGenerator.generate` 的 `target` 参数就是图的根节点。我们将捕获其逻辑 UUID 并将其记录在 `GraphIR` 中。
2.  **创建出口**: `ControlFlowWiringPolicy` 会检查一个节点是否是根节点。如果是，它会创建一个专用的 `egress.{logical_id}` 数据节点，并将该任务的 `Stainer` 的 `output_default` 端口连接到此节点。这为最终结果提供了一个明确的、可寻址的物理位置。
3.  **收集边界**: `Builder` 在完成所有布线后，通过简单的命名约定扫描（`startswith('const.')` 等）来识别所有的入口和出口数据节点，并将它们的信息系统地记录在 `Manifest` 中。

### 标签
#intent/architect #flow/ready #priority/high #comp/compiler #concept/state #scope/api #ai/instruct #task/domain/compiler #task/object/manifest #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `spec` 定义

首先，我们在 `cascade-spec` 中更新 `CompilationManifest` 和 `GraphIR` 的数据结构。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/assembly.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class CompilationManifest:
    # Maps logical UUIDs (from LazyResult) to the base physical node ID.
    # Key: Logical UUID
    # Value: Physical Base ID (current_node_instance_hash)
    logical_to_physical_map: Dict[str, str] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class CompilationManifest:
    # Maps logical UUIDs (from LazyResult) to the base physical node ID.
    # Key: Logical UUID
    # Value: Physical Base ID (current_node_instance_hash)
    logical_to_physical_map: Dict[str, str] = field(default_factory=dict)

    # List of physical DataNode IDs that are initial sources of energy (e.g., const, pulse)
    entry_points: List[str] = field(default_factory=list)

    # Maps the logical UUID of a root LazyResult to the physical DataNode ID
    # that will hold its final result.
    exit_points: Dict[str, str] = field(default_factory=dict)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class GraphIR:
    nodes: List[NodeIR] = field(default_factory=list)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class GraphIR:
    nodes: List[NodeIR] = field(default_factory=list)

    # The logical UUIDs of the LazyResults that were the entry points for generation.
    root_logical_ids: List[str] = field(default_factory=list)
~~~~~

#### Acts 2: 增强 `IRGenerator` 以识别根节点

修改 `generate` 方法以捕获根节点的 UUID。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
    def generate(self, target: Any) -> GraphIR:
        self._visit(target)
        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(nodes=list(self.nodes.values()))
~~~~~
~~~~~python.new
    def generate(self, target: Any) -> GraphIR:
        # If target is a list, treat all items as roots. Otherwise, wrap it.
        targets = target if isinstance(target, (list, tuple)) else [target]
        root_logical_ids = []

        for t in targets:
            if isinstance(t, LazyResult):
                root_logical_ids.append(t._uuid)
            self._visit(t)

        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(
            nodes=list(self.nodes.values()), root_logical_ids=root_logical_ids
        )
~~~~~

#### Acts 3: 修改 `ControlFlowWiringPolicy` 以创建 Egress 节点

为每个根节点创建一个物理出口。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~
~~~~~python.old
            ctx.wire.connect(
                source_subgraph.stainer.id, "output_default", d_cond_id, "in"
            )
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")
~~~~~
~~~~~python.new
            ctx.wire.connect(
                source_subgraph.stainer.id, "output_default", d_cond_id, "in"
            )
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")

        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"egress.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, "output_default", d_egress_id, "in")
~~~~~

#### Acts 4: 更新 `Builder` 以填充 Manifest

`Builder` 现在负责扫描图并填充 `entry_points` 和 `exit_points`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.physical.assembly import (
    Assembly,
    CompilationArtifact,
    CompilationManifest,
)
~~~~~
~~~~~python.new
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.assembly import (
    Assembly,
    CompilationArtifact,
    CompilationManifest,
)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        manifest = CompilationManifest(logical_to_physical_map=logical_to_physical_map)

        return CompilationArtifact(assembly=assembly, manifest=manifest)
~~~~~
~~~~~python.new
        entry_points = [
            node_id
            for node_id, node in physical_graph.nodes.items()
            if isinstance(node, PhysicsDataNode)
            and (node_id.startswith("const.") or node_id.startswith("pulse."))
        ]
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode) and node.id.startswith("egress.")
        }

        manifest = CompilationManifest(
            logical_to_physical_map=logical_to_physical_map,
            entry_points=sorted(entry_points),
            exit_points=exit_points,
        )

        return CompilationArtifact(assembly=assembly, manifest=manifest)
~~~~~

#### Acts 5: 添加集成测试

创建一个新的测试文件来验证 `Manifest` 的内容。

~~~~~act
write_file
packages/cascade-compiler/tests/integration/test_manifest_content.py
~~~~~
~~~~~python
import pytest

from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n

@task
def source():
    return "start"


def test_manifest_is_populated_correctly():
    # 1. Define a workflow with clear entry and exit points
    # Entry: source(), const 1, const 2
    # Exit: square()
    workflow = square(add(source(), 2))
    
    # We need the logical ID of the root to verify the exit point
    root_logical_id = workflow._uuid

    # 2. Compile
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
    manifest = artifact.manifest

    # 3. Assert Entry Points
    # We expect one pulse node (for source) and one const node (for value 2).
    # The first argument to add() is from source(), not a const.
    assert len(manifest.entry_points) == 2
    
    # Check that entries look correct
    assert any(ep.startswith("pulse.source.") for ep in manifest.entry_points)
    assert any(ep.startswith("const.") for ep in manifest.entry_points)
    
    # 4. Assert Exit Points
    assert len(manifest.exit_points) == 1
    assert root_logical_id in manifest.exit_points
    
    exit_node_id = manifest.exit_points[root_logical_id]
    assert exit_node_id.startswith("egress.")
    assert exit_node_id.endswith(root_logical_id)
~~~~~

### 下一步建议
我们已经成功地让编译器生成了包含完整边界信息的 `Manifest`。

下一步，我们可以解决 `Machine` 的低效轮询问题，引入 `asyncio.Event` 来实现真正的事件驱动调度，从而在系统空闲时降低 CPU 消耗。

我建议我们开始实施：**`Machine` 的轮询式休眠优化**。
