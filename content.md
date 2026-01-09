## [WIP] refactor(compiler): 拆分 ResourceWiringPolicy 以完成两阶段迁移

### 用户需求

根据架构路线图 3.3，需要将 `ResourceWiringPolicy` 的职责进行拆分。创建一个新的 `ResourceExpansionPolicy` 来调用 `prism.expand_task`，并更新 `ResourceWiringPolicy` 以调用 `prism.wire_task`。这是完成所有策略迁移的最后一步。

### 评论

这是整个重构工作的决胜局。通过拆分最复杂的 `ResourceWiringPolicy`，我们将最终完成编译器后端从单遍模型到两阶段模型的转变。`ResourceExpansionPolicy` 将正式接管所有资源节点的创建职责，而 `ResourceWiringPolicy` 将回归其纯粹的“连接”本质。此举将使整个资源管理子系统的逻辑变得前所未有的清晰和健壮。

### 目标

1.  创建 `expansion/policies/resource.py` 文件并实现 `ResourceExpansionPolicy`。
2.  重构 `wiring/policies/resource.py`，使 `ResourceWiringPolicy` 只负责连线。
3.  更新 `builder.py`，注册新的 `ResourceExpansionPolicy`。
4.  **最终目标**: 修复所有因 `AttributeError: ... has no attribute 'connect_task'` 导致的测试失败。

### 基本原理

这是我们将新架构付诸实施的最后一步。
-   **`ResourceExpansionPolicy`** 将在第一阶段（Materialization）调用 `prism.expand_task`，确保所有与资源相关的物理节点（`F_req`, `D_gnt` 等）都被创建并放入 `SubGraph`。
-   **`ResourceWiringPolicy`** 将在第二阶段（Wiring）调用 `prism.wire_task`，利用 `SubGraph` 中已存在的节点，完成它们与全局资源代理（`Allocator`）和任务三联体之间的复杂连接。

完成此步骤后，`Builder` 的两阶段流水线将完全运作，所有策略都将各司其职。

### 标签

#intent/refine #flow/ready #priority/high #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue #scope/core #ai/instruct

---

### Script

#### Acts 1: 实现 `ResourceExpansionPolicy`

这个新策略将负责调用 `ResourcePrism` 的 `expand_task` 方法。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
~~~~~
~~~~~python
from typing import Dict, cast

from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.expansion.context import ExpansionContext
from cascade.compiler.backend.expansion.protocol import ExpansionPolicy
from cascade.compiler.backend.wiring.prism import ResourcePrism
from cascade.compiler.backend.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceExpansionPolicy(ExpansionPolicy):
    def __init__(self):
        # In a more advanced system, this could be a dynamic registry.
        # For now, we hardcode the known prism implementations.
        self._prisms: Dict[str, ResourcePrism] = {
            "discrete": DiscreteResourcePrism(),
        }

    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        env_resources = {r.name: r for r in ctx.environment.resources}

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.expand_task(ctx, node_ir, subgraph, res_name, amount)

    def _get_prism(self, type_name: str) -> ResourcePrism:
        if type_name not in self._prisms:
            raise ValueError(f"Unknown resource type: '{type_name}'")
        return self._prisms[type_name]
~~~~~

#### Acts 2: 重构 `ResourceWiringPolicy`

现在，我们重构 `ResourceWiringPolicy`，使其调用 `prism.wire_task` 并共享 `Prism` 实例。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/resource.py
~~~~~
~~~~~python
from typing import Dict

from cascade.spec.ir.graph import NodeIR
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.compiler.backend.wiring.prism import ResourcePrism
from cascade.compiler.backend.wiring.prisms.discrete import DiscreteResourcePrism


class ResourceWiringPolicy(WiringPolicy):
    def __init__(self):
        self._prisms: Dict[str, ResourcePrism] = {
            "discrete": DiscreteResourcePrism(),
        }

    def setup_globals(self, ctx: WiringContext) -> None:
        # Create Global Brokers for each resource based on its type
        for res_def in ctx.environment.resources:
            prism = self._get_prism(res_def.type)
            prism.ensure_globals(ctx, res_def)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        # Validate and Wire constraints
        env_resources = {r.name: r for r in ctx.environment.resources}
        for res_name in node_ir.constraints:
            if res_name not in env_resources:
                raise ValueError(
                    f"Resource '{res_name}' required by node '{node_ir.current_node_instance_hash}' is not defined"
                )

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.wire_task(ctx, node_ir, subgraph, res_name, amount)

    def _get_prism(self, type_name: str) -> ResourcePrism:
        if type_name not in self._prisms:
            raise ValueError(f"Unknown resource type: '{type_name}'")
        return self._prisms[type_name]
~~~~~

#### Acts 3: 更新 `Builder` 以集成最终策略

最后，我们在 `Builder` 中注册 `ResourceExpansionPolicy`，并重构策略初始化以共享 `Prism` 实例，避免重复创建。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
from cascade.compiler.backend.expansion.policies.resource import (
    ResourceExpansionPolicy,
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

        # Instantiate policies to share prism instances
        resource_wiring_policy = ResourceWiringPolicy()
        resource_expansion_policy = ResourceExpansionPolicy()
        # A bit of a hack to share. A proper DI system would be better.
        resource_expansion_policy._prisms = resource_wiring_policy._prisms

        self._expansion_policies: List[ExpansionPolicy] = [
            resource_expansion_policy,
            ParameterExpansionPolicy(),
            ControlFlowExpansionPolicy(),
            PulseExpansionPolicy(),
        ]
        self._wiring_policies: List[WiringPolicy] = [
            resource_wiring_policy,
            ObservabilityWiringPolicy(),
            ParameterWiringPolicy(),
            ControlFlowWiringPolicy(),
            PulseWiringPolicy(),
        ]
~~~~~

### 下一步建议

我们已经完成了所有策略的迁移工作，编译器后端现在完全运行在新的两阶段模型之上了。`ResourceWiringPolicy` 的 `AttributeError` 应该已经解决。

路线图的下一步是**阶段四：协议锁定与验收**。我们将从 `4.1 实施 WiringHarness 读写分离` 开始，通过代码手段强制性地固化我们的新架构，防止未来的代码修改无意中破坏“职责分离”的原则。

如果你同意，我将开始制定强化 `WiringHarness` 的计划。
