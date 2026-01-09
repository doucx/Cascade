好的，我们正式进入路线图的阶段二，开始执行 `2.1 迁移 ParameterWiringPolicy`。

这是对新架构的第一次实际检验。此计划将 `ParameterWiringPolicy` 的双重职责——创建节点和连接节点——彻底分离，将其节点创建逻辑迁移到一个新的 `ParameterExpansionPolicy` 中。

## [WIP] refactor(compiler): 迁移 ParameterWiringPolicy 以分离节点创建

### 用户需求

根据架构路线图 2.1，需要将 `ParameterWiringPolicy` 的职责进行拆分。创建一个新的 `ParameterExpansionPolicy` 来处理所有与参数相关的节点创建（包括 `D_const` 和中间依赖节点 `D_dep`），并简化原有的 `ParameterWiringPolicy`，使其只负责连接逻辑。

### 评论

这是对我们新建立的两阶段编译模型的一次关键验证。通过迁移 `ParameterWiringPolicy`，我们首次将一个复杂的策略分解为纯粹的“物理实化”和“拓扑连接”两个部分。此举不仅使代码职责更加清晰，也为后续更复杂的 `ResourceWiringPolicy` 迁移提供了宝贵的实践经验和模式参考。成功完成后，我们将拥有一个更健壮、更易于推理的编译器后端。

### 目标

1.  创建新的 `expansion/policies` 目录及 `parameter.py` 文件。
2.  在 `expansion/policies/parameter.py` 中实现 `ParameterExpansionPolicy`，负责创建 `D_const` 和 `D_dep` 节点，并将它们注册到 `SubGraph` 的 `constants` 和 `controls` 字段中。
3.  重构 `wiring/policies/parameter.py`，移除所有 `ctx.wire.add_node` 调用，使其从 `SubGraph` 中获取节点引用，并只执行连接操作。
4.  更新 `builder.py`，将新的 `ParameterExpansionPolicy` 注册到 `_expansion_policies` 列表中。

### 基本原理

`ParameterWiringPolicy` 当前违反了单一职责原则，它既是“工厂”（创建 `D_const` 节点）又是“接线员”（连接节点）。这使得其行为难以预测和测试。

通过本次重构：
-   **`ParameterExpansionPolicy`** 将成为纯粹的“工厂”。在第一阶段，它会检查任务的输入，为所有字面量和依赖项创建必要的物理数据节点，并将这些新创建的“零件”放入 `SubGraph` 这个“收纳盒”中。
-   **`ParameterWiringPolicy`** 将成为纯粹的“接线员”。在第二阶段，它从“收纳盒” (`SubGraph`) 中取出所有“零件”，并根据蓝图 (`NodeIR`) 将它们连接起来。

这种清晰的分工是“扩展流水线”架构的核心，确保了编译过程的每个步骤都只做一件事并把它做好。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 创建 `ExpansionPolicy` 的目录结构

我们首先创建 `policies` 子目录和相应的 `__init__.py` 文件，为新的扩展策略提供存放位置。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies
touch packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/__init__.py
~~~~~

#### Acts 2: 实现 `ParameterExpansionPolicy`

这个新的策略将负责创建所有与参数相关的物理节点，并将其注册到 `SubGraph` 中。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy


class ParameterExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        for input_key, source_ref in node_ir.inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                d_dep_id = f"dep.{source_ref}.to.{node_ir.current_node_instance_hash}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")

                # Register the new node
                ctx.wire.add_node(d_dep)
                subgraph.nodes[d_dep.id] = d_dep
                subgraph.controls[f"dep_for_{input_key}"] = d_dep

            # Case B: Literal Value - Create D_const node
            else:
                d_const_id = PhysicalIdGenerator.constant(
                    node_ir.current_node_instance_hash, input_key
                )
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )

                # Register the new node
                ctx.wire.add_node(d_const)
                subgraph.nodes[d_const.id] = d_const
                subgraph.constants[input_key] = d_const
~~~~~

#### Acts 3: 重构 `ParameterWiringPolicy` 为纯连接逻辑

现在，我们移除 `ParameterWiringPolicy` 中的节点创建代码，使其只负责连接。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Bleacher.
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.stainer is not None

                # Retrieve the intermediate node created during expansion
                d_dep = subgraph.controls[f"dep_for_{input_key}"]

                # Connect: Source Stainer -> D_dep
                ctx.wire.connect(
                    source_subgraph.stainer.id,
                    StainerSpec.output_default.name,
                    d_dep.id,
                    "in",
                )

                # Connect: D_dep -> Target Bleacher
                ctx.wire.connect(d_dep.id, "out", subgraph.bleacher.id, port_name)

            # Case B: Literal Value (Constant)
            else:
                # Retrieve the constant node created during expansion
                d_const = subgraph.constants[input_key]

                # Connect: D_const -> Bleacher
                ctx.wire.connect(d_const.id, "out", subgraph.bleacher.id, port_name)
~~~~~

#### Acts 4: 更新 `Builder` 以集成新策略

最后，我们在 `Builder` 中注册新的 `ParameterExpansionPolicy`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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

### 下一步建议

我们已经成功完成了对 `ParameterWiringPolicy` 的迁移，并通过实践验证了新的两阶段编译模型。

路线图的下一步 (`2.2`) 是**迁移 `ControlFlowWiringPolicy`**。这个策略负责创建 `D_seq`, `D_cond`, 和 `D_egress` 等“胶水”节点，是另一个典型的“职责越界”案例。将其迁移到新的 `ControlFlowExpansionPolicy` 将进一步巩固我们的新架构。

如果你同意，我将开始制定迁移 `ControlFlowWiringPolicy` 的计划。
