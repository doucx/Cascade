好的，我们来执行路线图的 `1.3` 阶段，重构 `Builder`。

这个计划将对编译器 `Builder` 的核心执行流程进行手术刀式的改造，将其从一个单遍循环重构为职责清晰的“物理实化”和“拓扑连接”两个阶段。

## [WIP] refactor(compiler): 将 Builder 重构为两阶段编译模型

### 用户需求

根据架构路线图 1.3，需要重构 `cascade/compiler/backend/builder.py` 文件。目标是修改 `Builder` 的 `build` 方法，使其支持一个两阶段的编译流程：第一阶段进行节点创建（Materialization），第二阶段进行节点连接（Wiring）。

### 评论

这是整个重构计划中承上启下的关键一步。我们在此前已经定义了新的数据容器 (`SubGraph`) 和行为契约 (`ExpansionPolicy`)，现在则是要搭建能够驱动它们的执行引擎。将 `Builder` 改造为两阶段模型，是将“关注点分离”这一架构原则从理论落实到代码的关键，它为后续所有 `Policy` 的迁移铺平了道路，并能从根本上保证编译过程的确定性和可维护性。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/builder.py` 文件。
2.  导入新创建的 `ExpansionPolicy` 协议和 `ExpansionContext`。
3.  将 `Builder` 内部的策略列表 `_policies` 拆分为 `_expansion_policies` 和 `_wiring_policies` 两个独立的列表。
4.  重构 `build` 方法，将原有的单次循环拆分为两个独立的循环，分别对应 Materialization 和 Wiring 阶段。

### 基本原理

当前的 `Builder` 采用单遍编译模型，在一次循环中同时进行节点创建和连接。这种混合模式是导致 `WiringPolicy` 职责不清的根源。

通过引入两阶段编译模型，我们强制实施了架构上的约束：
1.  **第一阶段 (Materialization)**：只允许 `ExpansionPolicy` 运行，其唯一职责是创建物理节点并将其注册到 `SubGraph` 中。此阶段结束后，一个逻辑任务的所有物理实体都已“存在”，但彼此隔离。
2.  **第二阶段 (Wiring)**：只允许 `WiringPolicy` 运行，其唯一职责是连接已存在的节点。由于所有节点都已在第一阶段创建完毕，`WiringPolicy` 不再需要（也不被允许）创建任何新节点。

这种明确的分离使得每一阶段的输入和输出都变得确定，极大地降低了系统的复杂性。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/builder #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 重写 `builder.py` 以实现两阶段编译

我们将使用 `write_file` 完整覆盖 `builder.py`。新的实现将包含分离的策略列表和两阶段的 `build` 方法。`_expansion_policies` 列表暂时为空，等待后续步骤迁移策略进来。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python
from typing import List

from cascade.spec.ir.graph import GraphIR
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.assembly import (
    Assembly,
    CompilationArtifact,
    CompilationManifest,
)
from .expander import Expander
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.wiring.policies.parameter import ParameterWiringPolicy
from cascade.compiler.backend.wiring.policies.control import ControlFlowWiringPolicy
from cascade.compiler.backend.wiring.policies.observability import (
    ObservabilityWiringPolicy,
)
from cascade.compiler.backend.wiring.policies.resource import ResourceWiringPolicy
from cascade.compiler.backend.wiring.policies.pulse import PulseWiringPolicy
from cascade.spec.physical.constants import NodePrefix


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()
        self._expansion_policies: List[ExpansionPolicy] = []
        self._wiring_policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]

    def build(
        self, graph_ir: GraphIR, environment: EnvironmentDef
    ) -> CompilationArtifact:
        # 1. Initialize Context
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        # For now, ExpansionContext and WiringContext are identical.
        # We use a single context object for both phases.
        ctx = WiringContext(
            graph_ir=graph_ir,
            environment=environment,
            physical_graph=physical_graph,
            wire=wire,
        )
        symbol_table = {}

        # 2. Phase 0: Setup Global Infrastructure (for wiring policies)
        for policy in self._wiring_policies:
            policy.setup_globals(ctx)

        # 3. Phase 1: Materialization (Expansion)
        # Create all nodes for all subgraphs, but do not connect them across boundaries.
        for node_ir in graph_ir.nodes:
            # 3.1 Expand core triad
            subgraph = self._expander.expand_node(node_ir)
            ctx.register_subgraph(node_ir.current_node_instance_hash, subgraph)

            # 3.2 Populate Symbol Table from core triad
            if subgraph.worker:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.worker.id] = canonical_hash

            # 3.3 Apply expansion policies to create auxiliary nodes
            for policy in self._expansion_policies:
                policy.expand(ctx, node_ir, subgraph)

        # 4. Phase 2: Wiring
        # Connect all the created nodes together.
        for node_ir in graph_ir.nodes:
            subgraph = ctx.get_subgraph(node_ir.current_node_instance_hash)
            for policy in self._wiring_policies:
                policy.apply(ctx, node_ir, subgraph)

        # 5. Final Validation
        self._validator.validate(physical_graph, graph_ir)

        # 6. Generate Manifest
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
        entry_points = [
            node_id
            for node_id, node in physical_graph.nodes.items()
            if isinstance(node, PhysicsDataNode)
            and (
                node_id.startswith(f"{NodePrefix.CONST}.")
                or node_id.startswith(f"{NodePrefix.PULSE}.")
            )
        ]
        exit_points = {
            node.id.split(".")[1]: node.id
            for node in physical_graph.nodes.values()
            if isinstance(node, PhysicsDataNode)
            and node.id.startswith(f"{NodePrefix.EGRESS}.")
        }

        manifest = CompilationManifest(
            logical_to_physical_map=logical_to_physical_map,
            entry_points=sorted(entry_points),
            exit_points=exit_points,
        )

        return CompilationArtifact(assembly=assembly, manifest=manifest)
~~~~~

### 下一步建议

我们已经成功地将 `Builder` 重构为两阶段编译模型。现在，我们拥有了支持新架构的基础设施，但 `_expansion_policies` 列表还是空的，而 `_wiring_policies` 仍在承担着节点创建的职责。

路线图的下一步是**阶段二：简单策略迁移**，从 `2.1 迁移 ParameterWiringPolicy` 开始。这将是我们第一次在新架构上进行代码迁移，验证其是否按预期工作。

如果你同意，我将开始制定迁移 `ParameterWiringPolicy` 的计划。
