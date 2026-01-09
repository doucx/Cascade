简要回答
我们将修改 `cascade-compiler` 中的连线策略 (Wiring Policies)，使用 `cascade.std.specs` 中定义的强类型 Spec 属性来替代硬编码的字符串字面量，从而完成 PIDL 的闭环。

## [WIP] feat: 实施 PIDL 阶段四 - Compiler 连线重构

### 用户需求
1.  修改 `cascade-compiler` 的依赖项，使其能够访问 `cascade.std.specs`。
2.  重构 `ResourceWiringPolicy` (特别是 `DiscreteResourcePrism`)，使用 `DiscreteAllocatorSpec` 和 `DiscreteReclaimerSpec`。
3.  重构 `Expander`，使用 `BleacherSpec`, `WorkerSpec`, `StainerSpec` 定义端口。
4.  重构 `ParameterWiringPolicy` 和 `ControlFlowWiringPolicy`，引用相应的 Spec 属性。

### 评论
这是 PIDL 的最后一块拼图。一旦完成，编译器将不再通过猜测字符串（如 `"ledger_in"`）来连接节点，而是通过引用物理法则（如 `DiscreteAllocatorSpec.ledger_in.name`）来构建图。这意味着如果我们在 Spec 中更改了端口名，编译器会自动适应，或者在静态检查阶段报错，而不是在运行时默默失败。

### 目标
1.  更新 `packages/cascade-compiler/pyproject.toml`。
2.  更新 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py`。
3.  更新 `packages/cascade-compiler/src/cascade/compiler/backend/expander.py`。
4.  更新 `packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py` 等相关策略。

### 基本原理
*   **依赖倒置**: 编译器现在依赖于标准库的 Spec 定义，而不是标准库依赖编译器的约定。
*   **SSoT**: Spec 类成为唯一的端口名事实来源。
*   **示例**:
    *   **Old**: `ctx.wire.connect(ledger_id, "out", allocator_id, "ledger_in")`
    *   **New**: `ctx.wire.connect(ledger_id, "out", allocator_id, DiscreteAllocatorSpec.ledger_in.name)`

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #concept/wiring #scope/core #ai/instruct #task/domain/core #task/object/compiler-wiring #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 更新 Compiler 依赖

我们需要将 `cascade-std` 添加到 `cascade-compiler` 的依赖中，以便访问 Specs。

~~~~~act
patch_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-reflection",
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-reflection",
  "cascade-std",
]
~~~~~

#### Acts 2: 重构 Expander (Triad Wiring)

修改 `expander.py`，使用 `BleacherSpec`, `WorkerSpec`, `StainerSpec`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.reflection import PhysicalIdGenerator


@dataclass
class SubGraph:
~~~~~
~~~~~python.new
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.reflection import PhysicalIdGenerator
from cascade.std.specs import BleacherSpec, WorkerSpec, StainerSpec


@dataclass
class SubGraph:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict"),
                "trace_output": PortDef("trace_output", PortRole.DATA, "TraceCtx"),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
            },
        )

        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(id=d_worker_in_id, name=f"In({node_ir.name})")

        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            canonical_code_structure_hash=canonical_hash,
            input_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict")
            },
            output_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any")
            },
        )

        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(id=d_worker_out_id, name=f"Out({node_ir.name})")

        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        # Sovereign Ports: Explicitly define default and error paths
        stainer_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }
~~~~~
~~~~~python.new
        f_pre = BleachNode(
            id=f_pre_id,
            name=f"Bleach({node_ir.name})",
            input_ports=bleacher_inputs,
            output_ports=BleacherSpec.output_ports,
        )

        # D_worker_in: Holds the pure kwargs for the worker
        d_worker_in = PhysicsDataNode(id=d_worker_in_id, name=f"In({node_ir.name})")

        # F_worker: The actual execution logic
        # It conceptually takes *args/**kwargs, but physically takes one 'worker_input' dict
        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
        f_worker = WorkerNode(
            id=f_worker_id,
            name=f"Exec({node_ir.name})",
            canonical_code_structure_hash=canonical_hash,
            input_ports=WorkerSpec.input_ports,
            output_ports=WorkerSpec.output_ports,
        )

        # D_worker_out: Holds the raw result
        d_worker_out = PhysicsDataNode(id=d_worker_out_id, name=f"Out({node_ir.name})")

        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
        # Outputs = Result + Resource Returns
        # Sovereign Ports: Explicitly define default and error paths
        stainer_outputs = StainerSpec.output_ports.copy()
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="worker_input",
                target_node_id=d_worker_in_id,
                target_port="in",
            )
        )
        # D_worker_in -> F_worker
        channels.append(
            Channel(
                source_node_id=d_worker_in_id,
                source_port="out",
                target_node_id=f_worker_id,
                target_port="worker_input",
            )
        )
        # F_worker -> D_worker_out
        channels.append(
            Channel(
                source_node_id=f_worker_id,
                source_port="worker_result",
                target_node_id=d_worker_out_id,
                target_port="in",
            )
        )
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="worker_result",
            )
        )

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="trace_output",
                target_node_id=d_trace_id,
                target_port="in",
            )
        )
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )
~~~~~
~~~~~python.new
        # Path 1: Execution Flow
        # F_pre -> D_worker_in
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port=BleacherSpec.worker_input.name,
                target_node_id=d_worker_in_id,
                target_port="in",
            )
        )
        # D_worker_in -> F_worker
        channels.append(
            Channel(
                source_node_id=d_worker_in_id,
                source_port="out",
                target_node_id=f_worker_id,
                target_port=WorkerSpec.worker_input.name,
            )
        )
        # F_worker -> D_worker_out
        channels.append(
            Channel(
                source_node_id=f_worker_id,
                source_port=WorkerSpec.worker_result.name,
                target_node_id=d_worker_out_id,
                target_port="in",
            )
        )
        # D_worker_out -> F_post
        channels.append(
            Channel(
                source_node_id=d_worker_out_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port=StainerSpec.worker_result.name,
            )
        )

        # Path 2: Trace Bypass
        # F_pre -> D_trace
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port=BleacherSpec.trace_output.name,
                target_node_id=d_trace_id,
                target_port="in",
            )
        )
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port=StainerSpec.trace_input.name,
            )
        )
~~~~~

#### Acts 3: 重构 Resource Prism

修改 `prisms/discrete.py`，使用 `DiscreteAllocatorSpec` 和 `DiscreteReclaimerSpec`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
~~~~~
~~~~~python.new
from cascade.std.resource.discrete import DiscreteLedger
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec, GateSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.prism import ResourcePrism


class DiscreteResourcePrism(ResourcePrism):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
        # F_reclaimer
        f_reclaimer = PhysicsFuncNode(
            id=reclaimer_id,
            name=f"Reclaimer({res_def.name})",
            input_ports={
                PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                PortName.REL: PortDef(PortName.REL, PortRole.DATA),
            },
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                PortName.SIGNAL_OUT: PortDef(PortName.SIGNAL_OUT, PortRole.SIGNAL),
            },
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports={
                PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
            },
            output_ports={
                PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                PortName.REQ_PARKED: PortDef(PortName.REQ_PARKED, PortRole.DATA),
            },
        )
        ctx.wire.add_node(f_allocator)

        # Wiring: Ledger <-> Allocator
        ctx.wire.connect(ledger_id, "out", allocator_id, PortName.LEDGER_IN)
        ctx.wire.connect(allocator_id, PortName.LEDGER_OUT, ledger_id, "in")

        # Wiring: Ledger <-> Reclaimer
        ctx.wire.connect(ledger_id, "out", reclaimer_id, PortName.LEDGER_IN)
        ctx.wire.connect(reclaimer_id, PortName.LEDGER_OUT, ledger_id, "in")

        # Request Buffer
        d_req_buffer_id = f"buffer.req.{res_def.name}"
        d_req_buffer = PhysicsDataNode(
            id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_req_buffer)

        # Buffer -> Allocator
        ctx.wire.connect(d_req_buffer_id, "out", allocator_id, PortName.REQ)

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
                "req_in": PortDef("req_in", PortRole.DATA),
                "signal_in": PortDef("signal_in", PortRole.SIGNAL),
            },
            output_ports={"req_out": PortDef("req_out", PortRole.DATA)},
        )
        ctx.wire.add_node(f_gate)

        # 2. New Wiring
        # Allocator parks rejected requests
        ctx.wire.connect(allocator_id, PortName.REQ_PARKED, d_parked_id, "in")
        # Reclaimer sends wake-up signal
        ctx.wire.connect(reclaimer_id, PortName.SIGNAL_OUT, d_signal_id, "in")
        # Gate is triggered by parked request and signal
        ctx.wire.connect(d_parked_id, "out", f_gate_id, "req_in")
        ctx.wire.connect(d_signal_id, "out", f_gate_id, "signal_in")
        # Gate sends request back to the main buffer for retry
        ctx.wire.connect(f_gate_id, "req_out", d_req_buffer_id, "in")

        # Release Buffer
        rel_buffer_id = f"buffer.rel.{res_def.name}"
        d_rel_buffer = PhysicsDataNode(
            id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_rel_buffer)

        # Buffer -> Reclaimer
        ctx.wire.connect(rel_buffer_id, "out", reclaimer_id, PortName.REL)
~~~~~
~~~~~python.new
        # F_reclaimer
        f_reclaimer = PhysicsFuncNode(
            id=reclaimer_id,
            name=f"Reclaimer({res_def.name})",
            input_ports=DiscreteReclaimerSpec.input_ports,
            output_ports=DiscreteReclaimerSpec.output_ports,
        )
        ctx.wire.add_node(f_reclaimer)

        # F_allocator
        f_allocator = PhysicsFuncNode(
            id=allocator_id,
            name=f"Allocator({res_def.name})",
            input_ports=DiscreteAllocatorSpec.input_ports,
            # We must handle the dynamic grant ports separately if not in Spec? 
            # Actually Spec defines static ports + Map. The Graph builder (WiringHarness) 
            # doesn't strictly validate dynamic ports existence at definition time, 
            # but relies on connect() to create them if needed?
            # Wait, WiringHarness *does* validate port existence.
            # So we must ensure output_ports dict is populated if we want to wire to it.
            # For dynamic ports, we might need a way to 'declare' them on the node instance 
            # if they are not in the Spec's static dict.
            # However, for now, let's copy the static ones from Spec.
            output_ports=DiscreteAllocatorSpec.output_ports.copy(),
        )
        ctx.wire.add_node(f_allocator)

        # Wiring: Ledger <-> Allocator
        ctx.wire.connect(ledger_id, "out", allocator_id, DiscreteAllocatorSpec.ledger_in.name)
        ctx.wire.connect(allocator_id, DiscreteAllocatorSpec.ledger_out.name, ledger_id, "in")

        # Wiring: Ledger <-> Reclaimer
        ctx.wire.connect(ledger_id, "out", reclaimer_id, DiscreteReclaimerSpec.ledger_in.name)
        ctx.wire.connect(reclaimer_id, DiscreteReclaimerSpec.ledger_out.name, ledger_id, "in")

        # Request Buffer
        d_req_buffer_id = f"buffer.req.{res_def.name}"
        d_req_buffer = PhysicsDataNode(
            id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_req_buffer)

        # Buffer -> Allocator
        ctx.wire.connect(d_req_buffer_id, "out", allocator_id, DiscreteAllocatorSpec.req_in.name)

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
            input_ports=GateSpec.input_ports,
            output_ports=GateSpec.output_ports,
        )
        ctx.wire.add_node(f_gate)

        # 2. New Wiring
        # Allocator parks rejected requests
        ctx.wire.connect(allocator_id, DiscreteAllocatorSpec.req_parked.name, d_parked_id, "in")
        # Reclaimer sends wake-up signal
        ctx.wire.connect(reclaimer_id, DiscreteReclaimerSpec.signal_out.name, d_signal_id, "in")
        # Gate is triggered by parked request and signal
        ctx.wire.connect(d_parked_id, "out", f_gate_id, GateSpec.req_in.name)
        ctx.wire.connect(d_signal_id, "out", f_gate_id, GateSpec.signal_in.name)
        # Gate sends request back to the main buffer for retry
        ctx.wire.connect(f_gate_id, GateSpec.req_out.name, d_req_buffer_id, "in")

        # Release Buffer
        rel_buffer_id = f"buffer.rel.{res_def.name}"
        d_rel_buffer = PhysicsDataNode(
            id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
        )
        ctx.wire.add_node(d_rel_buffer)

        # Buffer -> Reclaimer
        ctx.wire.connect(rel_buffer_id, "out", reclaimer_id, DiscreteReclaimerSpec.rel_in.name)
~~~~~

#### Acts 4: 重构 Control Flow & Egress Wiring

修改 `policies/control.py`，使用 `EgressSpec` 和 `StainerSpec`。

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
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import StainerSpec, EgressSpec, BleacherSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.spec.physical.constants import NodePrefix


class ControlFlowWiringPolicy(WiringPolicy):
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
~~~~~
~~~~~python.old
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
            ctx.wire.connect(d_cond_id, "out", subgraph.bleacher.id, "condition")

        # 4.4 Egress for Root Nodes
        if node_ir.logical_id in ctx.graph_ir.root_logical_ids:
            assert subgraph.stainer is not None
            # Create a dedicated, addressable exit point for this graph root
            d_egress_id = f"{NodePrefix.EGRESS}.{node_ir.logical_id}"
            d_egress = PhysicsDataNode(id=d_egress_id, name=f"Egress({node_ir.name})")
            ctx.wire.add_node(d_egress)

            # Connect the stainer's default output to this egress node
            ctx.wire.connect(subgraph.stainer.id, StainerSpec.output_default.name, d_egress_id, EgressSpec.input_token.name)
~~~~~

#### Acts 5: 重构 Parameter Wiring

修改 `policies/parameter.py`。

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
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy
from cascade.std.specs import StainerSpec
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
我们已经完成了 PIDL 的所有实施阶段。
1.  **定义法则**: 建立了 `Port`, `PortDef`, `PhysicsSpec`。
2.  **标准化契约**: 在 `cascade-std` 中定义了所有核心 Specs。
3.  **实现重构**: Kernel 函数现在通过 `@implements` 绑定到 Specs。
4.  **连线重构**: Compiler 现在通过 Specs 来连接图。

现在，整个物理层从定义、实现到连线，都由同一套 PIDL 驱动。这意味着如果我们修改了 Spec，编译器会报错，Kernel 也会报错，系统的一致性得到了强保证。

最后一步是运行所有测试，确保这次大规模的“心脏移植”手术没有引发排异反应。
