from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ResourceWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        # Create Resource Brokers (Allocators + Reclaimers) for all resources in env
        for res_def in ctx.environment.resources:
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

            # F_reclaimer (Priority High: Must release before allocate to avoid starvation)
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

            # F_allocator (Priority Low)
            # NOTE: Dynamic grant ports (gnt_for_...) will be added during wiring phase
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    # PortName.GNT is deprecated in favor of dynamic ports, but kept for fallback
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

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None
        assert subgraph.stainer is not None

        # Validate resource existence
        # Note: We can't rely on Builder.build's early validation loop anymore
        # because the logic is distributed. We validate here locally.
        env_resource_names = {r.name for r in ctx.environment.resources}
        for res_name in node_ir.constraints:
            if res_name not in env_resource_names:
                raise ValueError(
                    f"Resource '{res_name}' required by node '{node_ir.id}' is not defined"
                )

        for res_name, amount in node_ir.constraints.items():
            allocator_id = PhysicalIdGenerator.global_allocator(res_name)
            req_buffer_id = f"buffer.req.{res_name}"
            rel_buffer_id = f"buffer.rel.{res_name}"

            # --- A. Request Chain ---
            # 1. D_const (Amount)
            d_amt_id = PhysicalIdGenerator.constant(node_ir.id, f"req_amt_{res_name}")
            d_amt = PhysicsDataNode(
                id=d_amt_id,
                name=f"Amt({res_name})",
                capacity=1,
                initial_tokens=1,
                initial_payload=amount,
            )
            ctx.wire.add_node(d_amt)

            # 2. F_probe (ConstProbe)
            f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
            f_probe = PhysicsFuncNode(
                id=f_probe_id,
                name=f"Probe({res_name})",
                input_ports={"value": PortDef("value", PortRole.DATA)},
                output_ports={"out": PortDef("out", PortRole.DATA)},
            )
            ctx.wire.add_node(f_probe)

            # 3. F_req (Requestor)
            f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
            f_req = PhysicsFuncNode(
                id=f_req_id,
                name=f"Req({res_name})",
                input_ports={"amount": PortDef("amount", PortRole.DATA)},
                output_ports={
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)
                },
            )
            ctx.wire.add_node(f_req)

            # 4. Wiring
            # D_amt -> F_probe
            ctx.wire.connect(d_amt_id, "out", f_probe_id, "value")

            # F_probe -> D_probed
            d_probed_id = f"{f_probe_id}.out"
            d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
            ctx.wire.add_node(d_probed)

            ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")

            # D_probed -> F_req
            ctx.wire.connect(d_probed_id, "out", f_req_id, "amount")

            # F_req -> D_req_buffer (Global Buffer for the Allocator)
            ctx.wire.connect(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")

            # --- B. Grant Wiring (Sovereign Ports) ---
            # 1. Define the dynamic port name on Allocator
            gnt_port_name = f"gnt_for_{f_req_id}"

            # 2. Add this port to the Allocator definition
            allocator_node = ctx.physical_graph.nodes[allocator_id]
            assert isinstance(allocator_node, PhysicsFuncNode)
            allocator_node.output_ports[gnt_port_name] = PortDef(
                gnt_port_name, PortRole.RESOURCE
            )

            # 3. Create a dedicated intermediate DataNode for this grant
            d_gnt_id = f"gnt.to.{node_ir.id}.{res_name}"
            d_gnt = PhysicsDataNode(
                id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})"
            )
            ctx.wire.add_node(d_gnt)

            # 4. Allocator -> Dedicated DataNode
            ctx.wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

            # 5. Dedicated DataNode -> Bleacher
            bleacher_port_name = f"res_{res_name}"
            ctx.wire.connect(
                d_gnt_id, "out", subgraph.bleacher.id, bleacher_port_name
            )

            # --- C. Release Wiring ---
            # Stainer -> RelBuffer
            release_port_name = f"res_{res_name}"
            ctx.wire.connect(
                subgraph.stainer.id,
                release_port_name,
                rel_buffer_id,
                "in",
            )