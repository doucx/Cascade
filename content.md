好的，我们采纳方案 A：**分布式脉冲模型**。

这是一个遵循“物理层纯粹性优于编译时性能”核心原则的正确决策。它确保了我们的编译器生成一个逻辑上完整且无歧义的物理图，将优化的复杂性正确地推迟到 JIT 阶段。

现在，我将生成一个计划来实现这个模型，专注于解决当前架构中最大的问题：“隐式启动”，特别是那些没有任何输入的“源任务”无法启动的问题。

我们将为每一个零输入的源任务创建一个专属的、自启动的脉冲节点，并将其连接到任务的预处理节点（Bleacher）上。这使得图的启动机制变得明确、健壮且符合物理定律。

## [WIP] refactor: 为源任务引入分布式脉冲以实现显式启动

### 用户需求
根据“分布式脉冲模型”策略，修改编译器为所有没有数据输入的源任务自动生成一个启动脉冲节点，以解决“隐式启动”和“僵尸节点”问题。

### 评论
这是实现“图的主权”的关键一步。通过将启动机制物化为图中的物理实体（脉冲节点），我们消除了对 `Reactor` 隐式行为的依赖。每个源任务现在都拥有自己明确的“点火器”，这使得整个计算物理场的演化完全由其内部拓扑和初始能量决定，变得更加自洽和可预测。

### 目标
1.  在 `cascade-spec` 中为脉冲端口定义一个标准的、稳定的名称 (`__pulse__`)。
2.  在 `cascade-compiler` 的命名工具中添加一个用于生成脉冲源 ID 的方法。
3.  修改 `Expander`，使其能识别零输入任务，并为其 `BleachNode` 添加一个 `__pulse__` 输入端口。
4.  修改 `Builder`，使其能识别零输入任务，为每个任务实例化一个带初始能量的 `PhysicsDataNode` 作为脉冲源，并将其连接到对应 `BleachNode` 的 `__pulse__` 端口。

### 基本原理
根据白皮书，“系统启动时，自动向所有无依赖的...发射一颗 Token”。当前架构的缺陷是，一个没有任何参数、依赖或约束的任务（例如，`@cs.task def source()`），其展开的 `BleachNode` 没有任何输入端口，因此永远无法满足“全准入激发”条件，成为一个“僵尸节点”。

本次重构通过以下方式解决此问题：
1.  **识别**: 编译器将识别出这些“零输入源节点”。
2.  **植入端口**: `Expander` 会为这些节点的 `BleachNode` 自动添加一个名为 `__pulse__` 的信号输入端口。
3.  **注入能量**: `Builder` 会为每个此类节点创建一个对应的 `Pulse` 数据节点，并预置 `initial_tokens=1`。
4.  **连接**: `Builder` 将 `Pulse` 节点连接到 `BleachNode` 的 `__pulse__` 端口。

这样，在系统启动时，`Reactor` 的 `prime()` 阶段会为所有脉冲节点注入能量，这些能量会通过物理连接流向并激活所有源任务，从而实现一个确定性的、并行的、物理上正确的启动流程。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/pulse-model #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Spec 中定义脉冲端口

首先，我们在 `ports.py` 中为脉冲信号定义一个标准名称，确保整个系统的引用一致性。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ports.py
~~~~~
~~~~~python.old
    # Observability
    OBS_OUTPUT = "obs_output"
    EVENT_TOKEN = "event_token"
~~~~~
~~~~~python.new
    # Observability
    OBS_OUTPUT = "obs_output"
    EVENT_TOKEN = "event_token"

    # System
    PULSE = "__pulse__"
~~~~~

#### Acts 2: 更新编译器命名工具

然后，我们为 `PhysicalIdGenerator` 添加一个方法来创建脉冲源节点的唯一 ID。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"
~~~~~
~~~~~python.new
    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"

    @staticmethod
    def pulse_source(logical_node_id: str) -> str:
        return f"pulse.source.{logical_node_id}"
~~~~~

#### Acts 3: 修改 Expander 以添加脉冲端口

现在，我们让 `Expander` 能够识别零输入任务，并为其 `BleachNode` 动态添加 `__pulse__` 端口。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.spec.ports import PortDef, PortRole
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~
~~~~~python.new
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.compiler.utils.naming import PhysicalIdGenerator
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # Add port for condition (SIGNAL/DATA)
        if node_ir.condition:
            port_name = "condition"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
~~~~~
~~~~~python.new
        # Add port for condition (SIGNAL/DATA)
        if node_ir.condition:
            port_name = "condition"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        # If after all that, there are no inputs, it's a source node that needs a pulse.
        if not bleacher_inputs:
            bleacher_inputs[PortName.PULSE] = PortDef(PortName.PULSE, PortRole.SIGNAL)

        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
~~~~~

#### Acts 4: 修改 Builder 以创建和连接脉冲源

最后，我们修改 `Builder` 来完成脉冲机制的物理布线。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
~~~~~
~~~~~python.new
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from cascade.spec.ports import PortName
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 3.3 Wire task observability TO the sidecar bus
            wire.connect(subgraph.bleacher.id, "obs_output", d_life_id, "in")
            wire.connect(subgraph.stainer.id, "obs_output", d_life_id, "in")

        # 4. Wire dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
~~~~~
~~~~~python.new
            # 3.3 Wire task observability TO the sidecar bus
            wire.connect(subgraph.bleacher.id, "obs_output", d_life_id, "in")
            wire.connect(subgraph.stainer.id, "obs_output", d_life_id, "in")

            # 3.4 Wire pulse for source nodes
            is_true_source = (
                not node_ir.inputs
                and not node_ir.dependencies
                and not node_ir.condition
                and not node_ir.constraints
            )
            if is_true_source:
                d_pulse_id = PhysicalIdGenerator.pulse_source(node_ir.id)
                d_pulse = PhysicsDataNode(
                    id=d_pulse_id,
                    name=f"Pulse({node_ir.id})",
                    capacity=1,
                    initial_tokens=1,
                )
                wire.add_node(d_pulse)
                wire.connect(d_pulse_id, "out", subgraph.bleacher.id, PortName.PULSE)

        # 4. Wire dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
~~~~~

### 下一步建议
我们已经成功地将“分布式脉冲”模型集成到了编译器中，解决了“隐式启动”这一核心架构违规。

根据我们的重构路线图，所有已识别的架构违规都已修正。我建议我们现在转向**验证**阶段。我们可以编写一个新的集成测试，该测试定义一个没有任何输入的源任务，并验证在 `Builder` 构建的物理图中，它被正确地连接到了一个自启动的 `Pulse` 节点，并且可以在 `Reactor` 中被成功激发。

这将确保我们的重构是正确且健壮的。如果你同意，我将为你生成这个测试计划。
