## [WIP] refactor(compiler): 实施 PIDL 阶段四 - Batch 3 (Resource & PortName Removal)

### 用户需求
完成 PIDL 阶段四的最后也是最复杂的部分：重构资源连线逻辑 (`ResourceWiringPolicy` 和 `DiscreteResourcePrism`)，并最终移除 `PortName` 类。
本批次涵盖：
- 补全缺失的 `ResourceRequestorSpec`。
- 更新 Kernel `resource_requestor` 以实现新 Spec。
- 重构 `Expander` 以使用 `BleacherSpec`。
- 重构 `DiscreteResourcePrism` 以使用 `DiscreteAllocatorSpec`, `DiscreteReclaimerSpec`, `ResourceRequestorSpec` 和 `GateSpec`。
- 删除 `cascade.spec.physical.ports.PortName`。

### 评论
这将彻底完成 Compiler 的“去魔法字符串”化。从此以后，所有的连线都由 `cascade-std` 中的 Specs 驱动。`PortName` 的移除是一个重要的里程碑，标志着旧时代的结束。

### 目标
1.  在 `cascade-std` 中定义 `ResourceRequestorSpec`。
2.  更新 `resource_requestor` kernel 实现。
3.  重构 `Expander` 和 `DiscreteResourcePrism`，替换所有 `PortName` 引用。
4.  删除 `cascade.spec.physical.ports` 中的 `PortName` 类。

### 基本原理
为了确保 Spec 覆盖率 100%，我们需要为 `Requestor` 节点补充定义。清理 `PortName` 可以防止未来的代码意外回退到使用字符串常量，强制开发者使用 Specs。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #comp/spec #scope/core #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 定义 ResourceRequestorSpec
我们需要为资源请求者节点定义契约。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/specs/resource.py
~~~~~
~~~~~python.old
    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)


class DiscreteReclaimerSpec(PhysicsSpec):
~~~~~
~~~~~python.new
    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)


class ResourceRequestorSpec(PhysicsSpec):
    """
    Contract for the Resource Requestor Node (F_req).
    Converts a static amount into a request token tagged with the requestor ID.
    """
    amount = Port.Input("amount", role=PortRole.DATA, type="int")
    req_out = Port.Output("req_out", role=PortRole.DATA, type=PortType.Token)


class DiscreteReclaimerSpec(PhysicsSpec):
~~~~~

#### Acts 2: 更新 resource_requestor 实现
使其实现新的 Spec。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    return {"req_out": Token(payload=amount_token.payload, trace=trace)}
~~~~~
~~~~~python.new
from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ResourceRequestorSpec
from cascade.std.kernel_tools import implements


@implements(ResourceRequestorSpec)
def resource_requestor(
    io: ResourceRequestorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    amount_token = io.amount

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    io.req_out = Token(payload=amount_token.payload, trace=trace)
~~~~~

#### Acts 3: 重构 Expander
替换 `PortName.PULSE`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.reflection import PhysicalIdGenerator
~~~~~
~~~~~python.new
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import BleacherSpec
from cascade.reflection import PhysicalIdGenerator
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # If after all that, there are no inputs, it's a source node that needs a pulse.
        if not bleacher_inputs:
            bleacher_inputs[PortName.PULSE] = PortDef(PortName.PULSE, PortRole.SIGNAL)

        f_pre = BleachNode(
~~~~~
~~~~~python.new
        # If after all that, there are no inputs, it's a source node that needs a pulse.
        if not bleacher_inputs:
            bleacher_inputs[BleacherSpec.pulse.name] = PortDef(BleacherSpec.pulse.name, PortRole.SIGNAL)

        f_pre = BleachNode(
~~~~~

#### Acts 4: 重构 DiscreteResourcePrism
这是最核心的替换工作。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
~~~~~
~~~~~python.new
from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.std.specs import (
    DiscreteAllocatorSpec,
    DiscreteReclaimerSpec,
    ResourceRequestorSpec,
    GateSpec,
)
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
class DiscreteResourcePrism(ResourcePrism):
    def ensure_globals(self, ctx: WiringContext, res_def: ResourceDef) -> None:
        allocator_id = PhysicalIdGenerator.global_allocator(res_def.name)
        reclaimer_id = PhysicalIdGenerator.global_reclaimer(res_def.name)
        ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

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

    def connect_task(
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

        # --- A. Request Chain ---
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
            input_ports={"amount": PortDef("amount", PortRole.DATA)},
            output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
        )
        ctx.wire.add_node(f_req)

        # 3. Wiring
        # D_amt -> F_req (Direct connection)
        ctx.wire.connect(d_amt_id, "out", f_req_id, "amount")

        # F_req -> D_req_buffer
        ctx.wire.connect(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")

        # --- B. Grant Wiring (Sovereign Ports) ---
        gnt_port_name = f"gnt_for_{f_req_id}"

        # Add this port to the Allocator definition
        allocator_node = ctx.physical_graph.nodes[allocator_id]
        assert isinstance(allocator_node, PhysicsFuncNode)
        allocator_node.output_ports[gnt_port_name] = PortDef(
            gnt_port_name, PortRole.RESOURCE
        )
~~~~~
~~~~~python.new
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
                reclaim.ledger_out.name: PortDef(reclaim.ledger_out.name, PortRole.DATA),
                reclaim.signal_out.name: PortDef(reclaim.signal_out.name, PortRole.SIGNAL),
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

    def connect_task(
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
        
        # --- A. Request Chain ---
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

        # 3. Wiring
        # D_amt -> F_req (Direct connection)
        ctx.wire.connect(d_amt_id, "out", f_req_id, req.amount.name)

        # F_req -> D_req_buffer
        ctx.wire.connect(f_req_id, req.req_out.name, req_buffer_id, "in")

        # --- B. Grant Wiring (Sovereign Ports) ---
        # Use prefix from Spec for dynamic port name
        spec = DiscreteAllocatorSpec
        gnt_port_name = f"{spec.grants.prefix}{f_req_id}"

        # Add this port to the Allocator definition
        allocator_node = ctx.physical_graph.nodes[allocator_id]
        assert isinstance(allocator_node, PhysicsFuncNode)
        allocator_node.output_ports[gnt_port_name] = PortDef(
            gnt_port_name, PortRole.RESOURCE
        )
~~~~~

#### Acts 5: 删除 PortName
这是最后的清理。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/ports.py
~~~~~
~~~~~python.old
@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"


class PortName:
    # Resources
    REQ = "req_in"
    REL = "rel_in"
    GNT = "gnt_out"
    REQ_OUT = "req_out"  # For recirculation
    REQ_PARKED = "req_parked"  # For parking rejected requests
    SIGNAL_OUT = "signal_out"  # For wake-up signals
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"

    # Worker
    WORKER_INPUT = "worker_input"
    WORKER_RESULT = "worker_result"

    # Trace
    TRACE_INPUT = "trace_input"
    TRACE_OUTPUT = "trace_output"

    # Observability
    OBS_OUTPUT = "obs_output"
    EVENT_TOKEN = "event_token"

    # System
    PULSE = "__pulse__"
~~~~~
~~~~~python.new
@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"
~~~~~

### 下一步建议
PIDL 阶段四已全面完成。现在可以进行全方位的测试，确保所有的 Spec 定义和 Compiler 连线完美匹配。之后，可以考虑进行阶段五：JIT 优化（利用新物理图的纯粹性）。
