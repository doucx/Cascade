from typing import Any

from cascade.spec.physical.environment import ResourceDef
from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.prism import ResourcePrism


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
                PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
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
        # Recirculation: Allocator -> Buffer
        ctx.wire.connect(allocator_id, PortName.REQ_OUT, d_req_buffer_id, "in")

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

        # Create a dedicated intermediate DataNode for this grant
        d_gnt_id = f"gnt.to.{node_ir.current_node_instance_hash}.{res_name}"
        d_gnt = PhysicsDataNode(id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})")
        ctx.wire.add_node(d_gnt)

        # Allocator -> Dedicated DataNode
        ctx.wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

        # Dedicated DataNode -> Bleacher
        assert subgraph.bleacher is not None
        bleacher_port_name = f"res_{res_name}"
        ctx.wire.connect(d_gnt_id, "out", subgraph.bleacher.id, bleacher_port_name)

        # --- C. Release Wiring ---
        # Stainer -> RelBuffer
        assert subgraph.stainer is not None
        release_port_name = f"res_{res_name}"
        ctx.wire.connect(
            subgraph.stainer.id,
            release_port_name,
            rel_buffer_id,
            "in",
        )
