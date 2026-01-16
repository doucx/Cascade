生成 Quipu 计划以执行 Step 3.4。

## [WIP] feat: 适配 Wiring Policies 与 Prisms 以支持 Dyad 架构

### 用户需求
执行 Dyad 架构重构的 Step 3.4。
在 `SubGraph` 模型和 `Expander` 逻辑更新后，现有的连线策略（Wiring Policies）和资源棱镜（Resource Prisms）因引用了不存在的 `bleacher`/`stainer` 字段而失效。需要将这些逻辑全部迁移到新的 `launcher`/`lander` 节点上。

### 评论
这是编译器重构的最后一步。完成此步骤后，编译器的 `Builder` 流程（扩展 -> 连线）将在 Dyad 架构下恢复通畅。我们需要特别注意资源棱镜（Prism）的修改，因为它是资源连线逻辑的实际承载者。

### 目标
1.  **更新核心策略**: 修改 `control.py`, `parameter.py`, `observability.py`, `pulse.py`，将旧的三联体节点引用替换为 `launcher`/`lander`，并更新端口引用。
2.  **更新资源棱镜**: 修改 `discrete.py` 中的 `wire_task` 方法，将资源请求连线重定向到 `launcher`，资源释放连线重定向自 `lander`。
3.  **修复 Import**: 确保所有文件正确导入新的 `LauncherSpec` 和 `LanderSpec`。

### 基本原理
连线策略是将独立的物理节点“缝合”成完整计算图的逻辑。
*   **输入侧**（参数、控制流依赖、资源请求）：原先连接到 `Bleacher`，现在连接到 `Launcher`。
*   **输出侧**（控制流触发、资源释放、可观测性）：原先连接自 `Stainer`，现在连接自 `Lander`。
*   **中间态**：原先的 `Worker` 和 `D_trace` 已被移除，不再需要相关连线逻辑。

### 标签
#intent/refine #flow/ready #priority/critical #comp/compiler #task/domain/compiler #task/object/wiring-policy #task/action/adapt #task/state/continue

---

### Script

#### Acts 1: 适配参数连线策略 (Parameter)

将参数（常量或依赖）连接到 `Launcher`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.specs.dyad import LanderSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.lander is not None

                # Retrieve the intermediate node created during expansion
                d_dep = subgraph.controls[f"dep_for_{input_key}"]

                # Connect: Source Lander -> D_dep
                # Note: LanderSpec uses 'output_default' just like StainerSpec did
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_dep.id,
                    "in",
                )

                # Connect: D_dep -> Target Launcher
                ctx.wire.connect(d_dep.id, "out", subgraph.launcher.id, port_name)

            # Case B: Literal Value (Constant)
            else:
                # Retrieve the constant node created during expansion
                d_const = subgraph.constants[input_key]

                # Connect: D_const -> Launcher
                ctx.wire.connect(d_const.id, "out", subgraph.launcher.id, port_name)
~~~~~

#### Acts 2: 适配控制流连线策略 (Control Flow)

依赖和条件连到 `Launcher`，Egress 连自 `Lander`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.spec.specs.dyad import LanderSpec, LauncherSpec
from cascade.spec.components import EgressSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ControlFlowWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        # 1. Sequence Dependencies (.after())
        for dep_id in node_ir.dependencies:
            if dep_id in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(dep_id)
                assert source_subgraph.lander is not None

                port_name = f"wait_for_{dep_id}"
                d_seq = subgraph.controls[f"seq_from_{dep_id}"]

                # Source Lander -> D_seq -> Target Launcher
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_seq.id,
                    "in",
                )
                ctx.wire.connect(d_seq.id, "out", subgraph.launcher.id, port_name)

        # 2. Condition (.run_if())
        if node_ir.condition and node_ir.condition in ctx.subgraphs:
            source_subgraph = ctx.get_subgraph(node_ir.condition)
            assert source_subgraph.lander is not None

            d_cond = subgraph.controls[f"cond_from_{node_ir.condition}"]

            # Source Lander -> D_cond -> Target Launcher
            ctx.wire.connect(
                source_subgraph.lander.id,
                LanderSpec.output_default.name,
                d_cond.id,
                "in",
            )
            ctx.wire.connect(
                d_cond.id, "out", subgraph.launcher.id, LauncherSpec.condition.name
            )

        # 3. Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.lander is not None
            d_egress = subgraph.controls[f"egress_for_{node_ir.logical_id}"]

            # Lander -> D_egress (which goes to F_egress)
            ctx.wire.connect(
                subgraph.lander.id,
                LanderSpec.output_default.name,
                d_egress.id,
                EgressSpec.input_token.name,
            )
~~~~~

#### Acts 3: 适配可观测性连线策略 (Observability)

Launcher (Started) 和 Lander (Finished) 都连接到 Observability Bus。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
~~~~~
~~~~~python
import sys
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.triad import ObservabilityNode
from cascade.spec.physical.ports import PortRole, PortDef
from cascade.spec.components import ObservabilitySpec
from cascade.spec.specs.dyad import LauncherSpec, LanderSpec
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class ObservabilityWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )

        # Use Spec to define ports
        spec = ObservabilitySpec
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                spec.event_token.name: PortDef(
                    spec.event_token.name, PortRole.OBSERVABILITY, "Event"
                )
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        ctx.wire.add_node(d_life)
        ctx.wire.add_node(f_obs)

        ctx.wire.connect(d_life_id, "out", f_obs_id, spec.event_token.name)

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None
        assert subgraph.lander is not None

        d_life_id = PhysicalIdGenerator.observability_bus()

        # Wire Launcher observability (STARTED event)
        ctx.wire.connect(
            subgraph.launcher.id, LauncherSpec.obs_output.name, d_life_id, "in"
        )
        
        # Wire Lander observability (FINISHED event)
        ctx.wire.connect(
            subgraph.lander.id, LanderSpec.obs_output.name, d_life_id, "in"
        )
~~~~~

#### Acts 4: 适配脉冲连线策略 (Pulse)

Pulse 连到 `Launcher`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
~~~~~
~~~~~python
from cascade.spec.ir.graph import NodeIR
from cascade.spec.specs.dyad import LauncherSpec
from ...expander import SubGraph
from ..context import WiringContext
from cascade.spec.compiler.interfaces import WiringPolicy


class PulseWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        # Check if a pulse source was created for this node during expansion
        if "pulse_source" in subgraph.controls:
            d_pulse = subgraph.controls["pulse_source"]
            ctx.wire.connect(
                d_pulse.id, "out", subgraph.launcher.id, LauncherSpec.pulse.name
            )
~~~~~

#### Acts 5: 适配离散资源棱镜 (Discrete Prism)

这是资源连线的核心。资源请求连到 `Launcher`，资源释放连自 `Lander`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python
from typing import Any

from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.components import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    GateSpec,
)
from cascade.std.resource.discrete import DiscreteLedger
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import WiringContext
from ...expansion.context import ExpansionContext
from cascade.spec.compiler.interfaces import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        allocator_id = PhysicalIdGenerator.global_allocator(res_def.name)
        reclaimer_id = PhysicalIdGenerator.global_reclaimer(res_def.name)
        ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

        # Specs shortcuts
        alloc = DiscreteAllocatorSpec
        reclaim = DiscreteReclaimerSpec
        gate = GateSpec

        # D_ledger
        initial_ledger = DiscreteLedger(
            total=res_def.capacity, available=res_def.capacity
        )
        d_ledger = PhysicsDataNode(
            id=ledger_id,
            name=f"Ledger({res_def.name})",
            capacity=1,
            initial_tokens=1,
            initial_payload=initial_ledger,
        )
        ctx.wire.add_node(d_ledger)

        # F_reclaimer
        f_reclaimer = PhysicsFuncNode(
            id=reclaimer_id,
            name=f"Reclaimer({res_def.name})",
            input_ports={
                reclaim.ledger_in.name: PortDef(reclaim.ledger_in.name, PortRole.DATA),
                reclaim.rel_in.name: PortDef(reclaim.rel_in.name, PortRole.DATA),
            },
            output_ports={
                reclaim.ledger_out.name: PortDef(
                    reclaim.ledger_out.name, PortRole.DATA
                ),
                reclaim.signal_out.name: PortDef(
                    reclaim.signal_out.name, PortRole.SIGNAL
                ),
            },
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports={
                alloc.ledger_in.name: PortDef(alloc.ledger_in.name, PortRole.DATA),
                alloc.req_in.name: PortDef(alloc.req_in.name, PortRole.DATA),
            },
            output_ports={
                alloc.ledger_out.name: PortDef(alloc.ledger_out.name, PortRole.DATA),
                alloc.gnt_out.name: PortDef(alloc.gnt_out.name, PortRole.RESOURCE),
                alloc.req_parked.name: PortDef(alloc.req_parked.name, PortRole.DATA),
            },
        )
        ctx.wire.add_node(f_allocator)

        # Wiring: Ledger <-> Allocator
        ctx.wire.connect(ledger_id, "out", allocator_id, alloc.ledger_in.name)
        ctx.wire.connect(allocator_id, alloc.ledger_out.name, ledger_id, "in")

        # Wiring: Ledger <-> Reclaimer
        ctx.wire.connect(ledger_id, "out", reclaimer_id, reclaim.ledger_in.name)
        ctx.wire.connect(reclaimer_id, reclaim.ledger_out.name, ledger_id, "in")

        # Request Buffer
        d_req_buffer_id = f"buffer.req.{res_def.name}"
        d_req_buffer = PhysicsDataNode(
            id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_req_buffer)

        # Buffer -> Allocator
        ctx.wire.connect(d_req_buffer_id, "out", allocator_id, alloc.req_in.name)

        # --- Parking & Wake-up Mechanism ---
        # 1. New Nodes
        d_parked_id = f"parked.req.{res_def.name}"
        d_parked = PhysicsDataNode(
            id=d_parked_id, name=f"Parked({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_parked)

        d_signal_id = f"signal.wakeup.{res_def.name}"
        d_signal = PhysicsDataNode(
            id=d_signal_id, name=f"Signal({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_signal)

        f_gate_id = f"gate.wakeup.{res_def.name}"
        f_gate = PhysicsFuncNode(
            id=f_gate_id,
            name=f"Gate({res_def.name})",
            input_ports={
                gate.req_in.name: PortDef(gate.req_in.name, PortRole.DATA),
                gate.signal_in.name: PortDef(gate.signal_in.name, PortRole.SIGNAL),
            },
            output_ports={gate.req_out.name: PortDef(gate.req_out.name, PortRole.DATA)},
        )
        ctx.wire.add_node(f_gate)

        # 2. New Wiring
        # Allocator parks rejected requests
        ctx.wire.connect(allocator_id, alloc.req_parked.name, d_parked_id, "in")
        # Reclaimer sends wake-up signal
        ctx.wire.connect(reclaimer_id, reclaim.signal_out.name, d_signal_id, "in")
        # Gate is triggered by parked request and signal
        ctx.wire.connect(d_parked_id, "out", f_gate_id, gate.req_in.name)
        ctx.wire.connect(d_signal_id, "out", f_gate_id, gate.signal_in.name)
        # Gate sends request back to the main buffer for retry
        ctx.wire.connect(f_gate_id, gate.req_out.name, d_req_buffer_id, "in")

        # Release Buffer
        rel_buffer_id = f"buffer.rel.{res_def.name}"
        d_rel_buffer = PhysicsDataNode(
            id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_rel_buffer)

        # Buffer -> Reclaimer
        ctx.wire.connect(rel_buffer_id, "out", reclaimer_id, reclaim.rel_in.name)

    def expand_task(
        self,
        ctx: ExpansionContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        # Spec shortcuts
        req = ResourceRequestorSpec

        # 1. D_const (Amount)
        d_amt_id = PhysicalIdGenerator.constant(
            node_ir.current_node_instance_hash, f"req_amt_{res_name}"
        )
        d_amt = PhysicsDataNode(
            id=d_amt_id,
            name=f"Amt({res_name})",
            capacity=1,
            initial_tokens=1,
            initial_payload=amount,
        )
        ctx.wire.add_node(d_amt)

        # 2. F_req (Requestor)
        f_req_id = PhysicalIdGenerator.requestor(
            node_ir.current_node_instance_hash, res_name
        )
        f_req = PhysicsFuncNode(
            id=f_req_id,
            name=f"Req({res_name})",
            input_ports={req.amount.name: PortDef(req.amount.name, PortRole.DATA)},
            output_ports={req.req_out.name: PortDef(req.req_out.name, PortRole.DATA)},
        )
        ctx.wire.add_node(f_req)

        # 3. D_gnt (Grant Recipient)
        d_gnt_id = f"gnt.to.{node_ir.current_node_instance_hash}.{res_name}"
        d_gnt = PhysicsDataNode(id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})")
        ctx.wire.add_node(d_gnt)

        # Register components in SubGraph
        subgraph.resources[res_name] = [d_amt, f_req, d_gnt]
        subgraph.nodes[d_amt_id] = d_amt
        subgraph.nodes[f_req_id] = f_req
        subgraph.nodes[d_gnt_id] = d_gnt

    def wire_task(
        self,
        ctx: WiringContext,
        node_ir: NodeIR,
        subgraph: SubGraph,
        res_name: str,
        amount: Any,
    ) -> None:
        allocator_id = PhysicalIdGenerator.global_allocator(res_name)
        req_buffer_id = f"buffer.req.{res_name}"
        rel_buffer_id = f"buffer.rel.{res_name}"

        # Spec shortcuts
        req = ResourceRequestorSpec

        # Retrieve components from SubGraph
        d_amt, f_req, d_gnt = subgraph.resources[res_name]
        d_amt_id = d_amt.id
        f_req_id = f_req.id
        d_gnt_id = d_gnt.id

        # --- A. Request Chain ---
        # D_amt -> F_req (Direct connection)
        ctx.wire.connect(d_amt_id, "out", f_req_id, req.amount.name)

        # F_req -> D_req_buffer
        ctx.wire.connect(f_req_id, req.req_out.name, req_buffer_id, "in")

        # --- B. Grant Wiring (Sovereign Ports) ---
        spec = DiscreteAllocatorSpec
        gnt_port_name = f"{spec.grants.prefix}{f_req_id}"

        allocator_node = ctx.physical_graph.nodes[allocator_id]
        assert isinstance(allocator_node, PhysicsFuncNode)
        allocator_node.output_ports[gnt_port_name] = PortDef(
            gnt_port_name, PortRole.RESOURCE
        )

        # Allocator -> Dedicated DataNode (D_gnt)
        ctx.wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

        # Dedicated DataNode -> Launcher
        assert subgraph.launcher is not None
        launcher_port_name = f"res_{res_name}"
        ctx.wire.connect(d_gnt_id, "out", subgraph.launcher.id, launcher_port_name)

        # --- C. Release Wiring ---
        # Lander -> RelBuffer
        assert subgraph.lander is not None
        release_port_name = f"res_{res_name}"
        ctx.wire.connect(
            subgraph.lander.id,
            release_port_name,
            rel_buffer_id,
            "in",
        )
~~~~~

### 下一步建议
编译器层的重构已接近完成，但还有一个关键的 **Linker** 适配步骤（Step 3.5）。目前编译器生成的节点 ID（`.launch`, `.land`）在运行时中还没有对应的 Python 实现映射。如果不修复 Linker，生成的图将无法在 VM 中运行。建议立即执行 Step 3.5。
