生成 Quipu 计划以执行 Step 3.2 和 Step 3.3。

## [WIP] feat: 实施 Dyad 架构的编译器模型重构与扩展逻辑

### 用户需求
执行 Dyad 架构重构的 Step 3.2 和 3.3。这涉及更新 `cascade-spec` 中的编译器中间模型 (`SubGraph`)，以及重写 `cascade-compiler` 中的核心扩展逻辑 (`Expander`)，使其生成二元体（Launcher-Lander）而非三联体（Bleacher-Worker-Stainer）拓扑。

### 评论
这是架构迁移中最具“破坏性”的一步。通过修改 `SubGraph` 定义和 `Expander` 逻辑，我们切断了旧架构的生成路径。虽然这会暂时导致下游的连线策略（Wiring Policies）失效（因为它们依赖旧的 `SubGraph` 结构），但这是为了确立新架构的骨架所必须的。下一步将修复连线策略以恢复系统完整性。

### 目标
1.  **重构模型**: 修改 `SubGraph` 类，移除 `bleacher`, `worker`, `stainer` 字段，替换为 `launcher`, `lander`。
2.  **重写扩展器**: 重写 `Expander.expand_node` 方法。
    *   使用新的 ID 生成器创建 `LauncherNode`, `LanderNode` 和 `ResultDataNode`。
    *   配置 `LauncherNode` 的属性（代码哈希、回复地址）和输入端口（参数、资源、依赖）。
    *   配置 `LanderNode` 的输出端口（结果、错误、资源归还）。
    *   建立 `D_result -> Lander` 的唯一物理连接。

### 基本原理
Dyad 架构的核心在于通过“隧道”机制传输上下文，从而消除物理层面的 Trace 旁路。`Expander` 的职责是实例化物理节点并定义其静态接口（端口）。新的扩展逻辑将不再生成 `D_trace` 和复杂的 `Bleach->Worker->Stain` 链，而是生成两个功能明确的端点：`Launcher` 负责打包上下文并发射，`Lander` 负责接收结果并着陆。

### 标签
#intent/architect #flow/ready #priority/critical #comp/compiler #comp/spec #task/domain/compiler #task/object/expander #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 SubGraph 模型

移除 Triad 相关的字段，引入 Dyad 字段。保留 `nodes`, `channels`, `constants` 等通用字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/compiler/model.py
~~~~~
~~~~~python.old
from ..physical.nodes import PhysicsNode, PhysicsDataNode
from ..physical.triad import BleachNode, WorkerNode, StainNode
from ..physical.topology import Channel


@dataclass
class SubGraph:
    bleacher: Optional[BleachNode] = None
    worker: Optional[WorkerNode] = None
    stainer: Optional[StainNode] = None

    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
~~~~~
~~~~~python.new
from ..physical.nodes import PhysicsNode, PhysicsDataNode
from ..physical.dyad import LauncherNode, LanderNode
from ..physical.topology import Channel


@dataclass
class SubGraph:
    launcher: Optional[LauncherNode] = None
    lander: Optional[LanderNode] = None

    constants: Dict[str, PhysicsDataNode] = field(default_factory=dict)
~~~~~

#### Acts 2: 重写 Expander 逻辑

完全重写 `expand_node` 方法以生成 Dyad 拓扑。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.compiler.model import SubGraph
from cascade.spec.specs.dyad import LauncherSpec, LanderSpec
from cascade.reflection import PhysicalIdGenerator


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        subgraph = SubGraph()

        # 1. Generate IDs for all physical entities
        base_id = node_ir.current_node_instance_hash

        f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
        d_result_id = PhysicalIdGenerator.result_data(base_id)
        f_land_id = PhysicalIdGenerator.lander_node(base_id)

        # 2. Create Launcher Node
        # Inputs = Task Args + Resource Constraints + Signals
        launcher_inputs = {}
        
        # 2.1 Static Args from Task Def
        for arg in node_ir.task.args:
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                continue
            launcher_inputs[arg.name] = PortDef(arg.name, PortRole.DATA, "Any")

        # 2.2 Dynamic Args from Inputs
        for input_key in node_ir.inputs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # 2.3 Resource Grants (RESOURCE_REQUEST role)
        # Note: The Launcher receives the grant token as DATA/RESOURCE to hold it.
        # In StdLib, we use PortRole.RESOURCE to identify held resources.
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            launcher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        # 2.4 Dependency Signals
        for dep_id in node_ir.dependencies:
            port_name = f"wait_for_{dep_id}"
            launcher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Token")

        # 2.5 Condition
        if node_ir.condition:
            port_name = "condition"
            launcher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        # 2.6 Pulse (if pure source)
        if not launcher_inputs:
            pulse_name = LauncherSpec.pulse.name
            launcher_inputs[pulse_name] = PortDef(
                pulse_name, PortRole.SIGNAL
            )

        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
        
        f_launcher = LauncherNode(
            id=f_launch_id,
            name=f"Launch({node_ir.name})",
            input_ports=launcher_inputs,
            # Launcher only has observability output locally.
            # Data output is evaporated to the Queue.
            output_ports={
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event")
            },
            canonical_code_structure_hash=canonical_hash,
            reply_to_nid=d_result_id
        )

        # 3. Create Result Data Node (The Landing Pad)
        d_result = PhysicsDataNode(id=d_result_id, name=f"Result({node_ir.name})")

        # 4. Create Lander Node
        # Outputs = Default + Error + Resource Returns + Obs
        lander_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
        
        # 4.1 Resource Returns
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            # Role RESOURCE indicates this is a return path
            lander_outputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        f_lander = LanderNode(
            id=f_land_id,
            name=f"Land({node_ir.name})",
            input_ports={
                # Lander receives the raw result token
                LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA, "Any")
            },
            output_ports=lander_outputs,
        )

        # 5. Register Nodes
        subgraph.nodes = {
            f_launch_id: f_launcher,
            d_result_id: d_result,
            f_land_id: f_lander
        }
        subgraph.launcher = f_launcher
        subgraph.lander = f_lander

        # 6. Internal Wiring
        # Only one physical connection inside the Dyad: D_result -> Lander
        subgraph.channels = [
            Channel(
                source_node_id=d_result_id,
                source_port="out",
                target_node_id=f_land_id,
                target_port=LanderSpec.result_token.name,
            )
        ]

        return subgraph
~~~~~

### 下一步建议

现在 `SubGraph` 模型和 `Expander` 逻辑已经切换到 Dyad 架构，但系统目前处于不一致状态：`cascade-compiler` 中的 **Wiring Policies** (如 `control.py`, `parameter.py` 等) 仍然试图访问不存在的 `subgraph.bleacher` 或 `subgraph.stainer`。

接下来的任务必须是 **Step 3.4: 连线策略适配**，我们需要逐个修改 `wiring/policies/` 下的所有策略文件，将旧的连接逻辑映射到新的 `launcher` 和 `lander` 节点上。如果不执行此步骤，编译器将无法运行。
