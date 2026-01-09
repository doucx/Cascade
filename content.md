好的，我们来执行路线图的 `2.3` 阶段，完成所有简单策略的迁移。

此计划将处理 `PulseWiringPolicy`，它负责为工作流的“源头”任务提供初始动力。我们将把它拆分为创建和连接两个部分，为阶段二画上一个圆满的句号。

## [WIP] refactor(compiler): 迁移 PulseWiringPolicy 以分离节点创建

### 用户需求

根据架构路线图 2.3，需要将 `PulseWiringPolicy` 的职责进行拆分。创建一个新的 `PulseExpansionPolicy` 来负责识别源节点并为其创建 `D_pulse` 启动节点，并简化原有的 `PulseWiringPolicy`，使其只负责连接这个 `D_pulse` 节点。

### 评论

这次迁移虽然简单，但意义重大。它标志着我们完成了所有非资源型策略的重构。至此，所有关于参数、控制流和启动脉冲的物理节点都在确定性的“物理实化”阶段被创建。这为我们接下来处理最复杂的 `ResourceWiringPolicy` 扫清了所有障碍，使我们能够以一个干净、稳定的架构基础来迎接最大的挑战。

### 目标

1.  创建 `expansion/policies/pulse.py` 文件。
2.  在其中实现 `PulseExpansionPolicy`，负责识别“真正”的源节点并为其创建 `D_pulse` 节点，然后将其注册到 `SubGraph` 的 `controls` 字典中。
3.  重构 `wiring/policies/pulse.py`，移除节点创建和源节点识别逻辑，使其仅在 `SubGraph` 中发现 `D_pulse` 节点时执行连接操作。
4.  更新 `builder.py`，将新的 `PulseExpansionPolicy` 注册到 `_expansion_policies` 列表中。

### 基本原理

当前的 `PulseWiringPolicy` 在连接阶段动态地判断一个节点是否需要启动脉冲，并即时创建 `D_pulse` 节点。这使得图的“能量源”在最后一刻才被确定下来。

通过本次重构：
-   **`PulseExpansionPolicy`** 将在第一阶段就明确地识别出所有源节点，并为它们打上“启动”标记——即，在它们的 `SubGraph` 中创建一个 `D_pulse` 节点。
-   **`PulseWiringPolicy`** 在第二阶段只需检查这个标记是否存在。如果存在，就将脉冲源连接到任务的启动端口上。

这种模式将“识别”与“执行”分离，使得整个流程更加清晰和健壮。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 实现 `PulseExpansionPolicy`

这个新策略将负责识别源节点并为其创建 `D_pulse` 节点。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy


class PulseExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # A true source has no inputs, dependencies, conditions, or constraints.
        is_true_source = (
            not node_ir.inputs
            and not node_ir.dependencies
            and not node_ir.condition
            and not node_ir.constraints
        )

        if is_true_source:
            d_pulse_id = PhysicalIdGenerator.pulse_source(
                node_ir.current_node_instance_hash
            )
            d_pulse = PhysicsDataNode(
                id=d_pulse_id,
                name=f"Pulse({node_ir.current_node_instance_hash})",
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            subgraph.nodes[d_pulse.id] = d_pulse
            subgraph.controls["pulse_source"] = d_pulse
~~~~~

#### Acts 2: 重构 `PulseWiringPolicy` 为纯连接逻辑

现在，我们简化 `PulseWiringPolicy`，使其只负责连接。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.std.specs import BleacherSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class PulseWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        # Check if a pulse source was created for this node during expansion
        if "pulse_source" in subgraph.controls:
            d_pulse = subgraph.controls["pulse_source"]
            ctx.wire.connect(
                d_pulse.id, "out", subgraph.bleacher.id, BleacherSpec.pulse.name
            )
~~~~~

#### Acts 3: 更新 `Builder` 以集成新策略

最后，我们在 `Builder` 中注册新的 `PulseExpansionPolicy`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
from cascade.compiler.backend.expansion.policies.pulse import PulseExpansionPolicy
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
            PulseExpansionPolicy(),
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

我们已经成功完成了阶段二的所有任务。所有简单的 `WiringPolicy` 都已成功迁移，我们的两阶段编译架构也经受住了考验。

现在，是时候进入路线图的**阶段三：复杂策略迁移**了。这将是本次重构中最具挑战性但也最有价值的部分。我们将从 `3.1 重构 ResourcePrism 协议` 开始，为 `ResourceWiringPolicy` 的迁移做准备。

如果你同意，我将开始制定重构 `ResourcePrism` 协议的计划。
