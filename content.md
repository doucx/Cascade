好的，我们继续执行路线图 `2.2`。

此计划将处理负责序列依赖、条件执行和图出口的 `ControlFlowWiringPolicy`。我们将遵循已建立的模式，将其节点创建功能迁移到新的 `ControlFlowExpansionPolicy` 中，进一步净化 `Wiring` 阶段的职责。

## [WIP] refactor(compiler): 迁移 ControlFlowWiringPolicy 以分离节点创建

### 用户需求

根据架构路线图 2.2，需要将 `ControlFlowWiringPolicy` 的职责进行拆分。创建一个新的 `ControlFlowExpansionPolicy` 来处理所有与控制流相关的“胶水”节点（`D_seq`, `D_cond`, `D_egress`）的创建，并简化原有的 `ControlFlowWiringPolicy`，使其只负责连接逻辑。

### 评论

这次迁移是巩固新架构的又一重要步骤。控制流节点是连接不同子图的“韧带”，将它们的创建过程从动态的连接阶段前置到确定性的物理实化阶段，能极大地增强编译过程的稳定性和可预测性。这使得物理图的拓扑结构在 `Wiring` 阶段开始之前就已完全确定，是实现一个真正健壮的编译器后端的必要条件。

### 目标

1.  创建 `expansion/policies/control.py` 文件。
2.  在其中实现 `ControlFlowExpansionPolicy`，负责创建 `D_seq` (for `.after()`), `D_cond` (for `.run_if()`), 和 `D_egress` (for root nodes) 节点，并将它们注册到 `SubGraph` 的 `controls` 字典中。
3.  重构 `wiring/policies/control.py`，移除所有节点创建代码，使其从 `SubGraph` 中获取已存在的控制流节点，并只执行连接操作。
4.  更新 `builder.py`，将新的 `ControlFlowExpansionPolicy` 注册到 `_expansion_policies` 列表中。

### 基本原理

`ControlFlowWiringPolicy` 当前扮演着“胶水工厂”的角色，在需要连接时才即时创建 `D_seq` 等节点。这种“边造边用”的模式使得编译过程的中间状态变得模糊。

通过本次重构：
-   **`ControlFlowExpansionPolicy`** 将在第一阶段（Materialization）为每个 `NodeIR` 预先创建所有必要的控制流节点。这些节点将被视为 `SubGraph` 物理形态的一部分，并被妥善保管。
-   **`ControlFlowWiringPolicy`** 将在第二阶段（Wiring）中，像一个装配工一样，从 `SubGraph` 中取出这些预制好的“胶水”节点，并将它们精确地连接在不同的子图之间。

这种“先制造，后装配”的流水线模式，确保了每个阶段的职责都高度内聚，从而降低了整个系统的复杂度。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 实现 `ControlFlowExpansionPolicy`

这个新策略将负责创建所有与控制流相关的物理节点，并将其注册到 `SubGraph` 中。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.constants import NodePrefix
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy


class ControlFlowExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            d_seq_id = f"seq.{dep_id}.to.{node_ir.current_node_instance_hash}"
            d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
            ctx.wire.add_node(d_seq)
            subgraph.nodes[d_seq.id] = d_seq
            subgraph.controls[f"seq_from_{dep_id}"] = d_seq

        # 2. Condition (.run_if())
        if node_ir.condition:
            d_cond_id = (
                f"cond.{node_ir.condition}.to.{node_ir.current_node_instance_hash}"
            )
            d_cond = PhysicsDataNode(
                id=d_cond_id, name=f"Cond({node_ir.condition})"
            )
            ctx.wire.add_node(d_cond)
            subgraph.nodes[d_cond.id] = d_cond
            subgraph.controls[f"cond_from_{node_ir.condition}"] = d_cond

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)
            subgraph.nodes[d_egress.id] = d_egress
            subgraph.controls[f"egress_for_{node_ir.logical_id}"] = d_egress
~~~~~

#### Acts 2: 重构 `ControlFlowWiringPolicy` 为纯连接逻辑

现在，我们移除 `ControlFlowWiringPolicy` 中的节点创建代码。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import StainerSpec, BleacherSpec, EgressSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"
                d_seq = subgraph.controls[f"seq_from_{dep_id}"]

                ctx.wire.connect(
                    source_subgraph.stainer.id,
                    StainerSpec.output_default.name,
                    d_seq.id,
                    "in",
                )
                ctx.wire.connect(d_seq.id, "out", subgraph.bleacher.id, port_name)

        # 2. Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            d_cond = subgraph.controls[f"cond_from_{node_ir.condition}"]

            ctx.wire.connect(
                source_subgraph.stainer.id,
                StainerSpec.output_default.name,
                d_cond.id,
                "in",
            )
            ctx.wire.connect(
                d_cond.id, "out", subgraph.bleacher.id, BleacherSpec.condition.name
            )

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            d_egress = subgraph.controls[f"egress_for_{node_ir.logical_id}"]

            ctx.wire.connect(
                subgraph.stainer.id,
                StainerSpec.output_default.name,
                d_egress.id,
                EgressSpec.input_token.name,
            )
~~~~~

#### Acts 3: 更新 `Builder` 以集成新策略

最后，我们在 `Builder` 中注册新的 `ControlFlowExpansionPolicy`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.expansion.policies.parameter import (
    ParameterExpansionPolicy,
)
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
        self._expansion_policies: List[ExpansionPolicy] = [
            ParameterExpansionPolicy(),
        ]
        self._wiring_policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]
~~~~~
~~~~~python.new
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.expansion.policies.parameter import (
    ParameterExpansionPolicy,
)
from cascade.compiler.backend.expansion.policies.control import (
    ControlFlowExpansionPolicy,
)
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
        self._expansion_policies: List[ExpansionPolicy] = [
            ParameterExpansionPolicy(),
            ControlFlowExpansionPolicy(),
        ]
        self._wiring_policies: List[WiringPolicy] = [
            ResourceWiringPolicy(),
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]
~~~~~

### 下一步建议

我们已经成功地将 `ControlFlowWiringPolicy` 的职责分离。现在，编译器的两个核心策略（参数和控制流）都已经适配了新的两阶段模型。

路线图的下一步 (`2.3`) 是**迁移 `PulseWiringPolicy`**。这是一个逻辑非常简单的策略，只负责为源节点创建 `D_pulse` 启动节点。迁移它将是一项快速的工作，能够让我们完成所有“简单策略”的迁移，为 tackling 复杂的 `ResourceWiringPolicy` 做好充分准备。

如果你同意，我将开始制定迁移 `PulseWiringPolicy` 的计划。
