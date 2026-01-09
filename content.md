## [WIP] refactor(compiler): 实施 PIDL 阶段四 - Batch 2 (Control & Parameter)

### 用户需求
继续 PIDL 阶段四的重构工作，重点是将 Control Flow 和 Parameter 连线逻辑中的硬编码字符串替换为 Spec 引用。
本批次涵盖：
- `ControlFlowWiringPolicy` 的重构：替换 `output_default`, `condition` 以及 Egress 相关的 `in`。
- `ParameterWiringPolicy` 的重构：替换 `output_default`。

### 评论
通过引入 `StainerSpec` 和 `BleacherSpec`，我们确保了控制流和数据依赖的连线是类型安全的。对于 `Egress` 节点，我们使用 `EgressSpec` 来确保端口一致性。

### 目标
1.  重构 `ControlFlowWiringPolicy`，使用 `StainerSpec.output_default.name` 和 `BleacherSpec.condition.name`。
2.  重构 `ParameterWiringPolicy`，使用 `StainerSpec.output_default.name`。
3.  在连接 Egress 节点时，使用 `EgressSpec.input_token.name`。

### 基本原理
消除魔法字符串，确保编译器后端与标准库定义保持同步。这不仅提高了代码的可维护性，也为未来可能的端口重命名提供了单点修改的能力。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #scope/core #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 ControlFlowWiringPolicy
我们将引入 `StainerSpec`, `BleacherSpec` 和 `EgressSpec`。
注意：`"wait_for_"` 前缀目前保留为字符串构建，因为它涉及动态 ID 拼接，且尚未在 Spec 中定义为常量。但核心端口必须替换。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.spec.physical.constants import NodePrefix


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 4.2 Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"

                # Violation Fix: Insert D_seq
                d_seq_id = f"seq.{dep_id}.to.{node_ir.current_node_instance_hash}"
                d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                ctx.wire.add_node(d_seq)

                ctx.wire.connect(
                    source_subgraph.stainer.id, "output_default", d_seq_id, "in"
                )
                ctx.wire.connect(d_seq_id, "out", subgraph.bleacher.id, port_name)

        # 4.3 Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            # Violation Fix: Insert D_cond
            d_cond_id = (
                f"cond.{node_ir.condition}.to.{node_ir.current_node_instance_hash}"
            )
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)

            ctx.wire.connect(
                source_subgraph.stainer.id, "output_default", d_cond_id, "in"
            )
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")

        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, "output_default", d_egress_id, "in")
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import StainerSpec, BleacherSpec, EgressSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.spec.physical.constants import NodePrefix


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # 4.2 Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.stainer is not None

                port_name = f"wait_for_{dep_id}"

                # Violation Fix: Insert D_seq
                d_seq_id = f"seq.{dep_id}.to.{node_ir.current_node_instance_hash}"
                d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                ctx.wire.add_node(d_seq)

                ctx.wire.connect(
                    source_subgraph.stainer.id, StainerSpec.output_default.name, d_seq_id, "in"
                )
                ctx.wire.connect(d_seq_id, "out", subgraph.bleacher.id, port_name)

        # 4.3 Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.stainer is not None

            # Violation Fix: Insert D_cond
            d_cond_id = (
                f"cond.{node_ir.condition}.to.{node_ir.current_node_instance_hash}"
            )
            d_cond = PhysicsDataNode(id=d_cond_id, name=f"Cond({node_ir.condition})")
            ctx.wire.add_node(d_cond)

            ctx.wire.connect(
                source_subgraph.stainer.id, StainerSpec.output_default.name, d_cond_id, "in"
            )
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, BleacherSpec.condition.name)

        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            # Using EgressSpec.input_token.name for the target port (usually "in")
            ctx.wire.connect(
                subgraph.stainer.id, 
                StainerSpec.output_default.name, 
                d_egress_id, 
                EgressSpec.input_token.name
            )
~~~~~

#### Acts 2: 重构 ParameterWiringPolicy
引入 `StainerSpec` 替换 `output_default`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(
                    source_subgraph.stainer.id, "output_default", d_dep_id, "in"
                )

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, port_name)
~~~~~
~~~~~python.new
                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(
                    source_subgraph.stainer.id, StainerSpec.output_default.name, d_dep_id, "in"
                )

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, port_name)
~~~~~

### 下一步建议
Batch 2 完成。现在所有的核心逻辑连线（Control, Parameter, Observability, Pulse）都已经使用了 Specs。
最后一个，也是最大的 Batch 是重构 `ResourceWiringPolicy` (Batch 3)。这将涉及大量的端口名替换（ledger_in, req_in, gnt_out 等），并最终允许我们删除过时的 `PortName` 常量类。
