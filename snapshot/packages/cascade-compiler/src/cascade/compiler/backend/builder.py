import sys
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from .validator import GraphValidator
from .wiring import WiringHarness
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()
        self._validator = GraphValidator()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        wire = WiringHarness(physical_graph)
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Resource Brokers (Allocators + Reclaimers)
        for res_def in environment.resources:
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
            wire.add_node(d_ledger)

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
            wire.add_node(f_reclaimer)

            # F_allocator (Priority Low)
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
            wire.add_node(f_allocator)

            # Wiring: Ledger <-> Allocator
            wire.connect(ledger_id, "out", allocator_id, PortName.LEDGER_IN)
            wire.connect(allocator_id, PortName.LEDGER_OUT, ledger_id, "in")

            # Wiring: Ledger <-> Reclaimer
            wire.connect(ledger_id, "out", reclaimer_id, PortName.LEDGER_IN)
            wire.connect(reclaimer_id, PortName.LEDGER_OUT, ledger_id, "in")

            # Request Buffer
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )
            wire.add_node(d_req_buffer)

            # Buffer -> Allocator
            wire.connect(d_req_buffer_id, "out", allocator_id, PortName.REQ)
            # Recirculation: Allocator -> Buffer
            wire.connect(allocator_id, PortName.REQ_OUT, d_req_buffer_id, "in")

            # Release Buffer
            rel_buffer_id = f"buffer.rel.{res_def.name}"
            d_rel_buffer = PhysicsDataNode(
                id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
            )
            wire.add_node(d_rel_buffer)

            # Buffer -> Reclaimer
            wire.connect(rel_buffer_id, "out", reclaimer_id, PortName.REL)

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = PhysicalIdGenerator.observability_bus()
        f_obs_id = PhysicalIdGenerator.observability_observer()

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={
                "event_token": PortDef("event_token", PortRole.OBSERVABILITY, "Event")
            },
            output_ports={},  # Observer emits to the outside world, not back into the graph
        )
        wire.add_node(d_life)
        wire.add_node(f_obs)

        wire.connect(d_life_id, "out", f_obs_id, "event_token")

        # 3. Expand all logical nodes into physical subgraphs
        subgraphs: Dict[str, SubGraph] = {}
        for node_ir in graph_ir.nodes:
            # 3.1 Validate resource constraints against the environment
            for res_name in node_ir.constraints:
                if res_name not in env_resources:
                    raise ValueError(
                        f"Resource '{res_name}' required by node '{node_ir.id}' is not defined"
                    )

            # 3.2 Expand
            subgraph = self._expander.expand_node(node_ir)
            if subgraph.bleacher is None or subgraph.stainer is None:
                raise RuntimeError(f"Subgraph for {node_ir.id} is incomplete.")

            # Help static analysis verify these are not None
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            subgraphs[node_ir.id] = subgraph
            wire.add_subgraph(subgraph)

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
            assert target_subgraph.bleacher is not None

            # 4.1 Data Dependencies (Arguments)
            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
                    assert source_subgraph.stainer is not None

                    # Violation Fix: Insert D_dep (Intermediate Data Node)
                    d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{arg_name}"
                    d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                    wire.add_node(d_dep)

                    # Source Stainer -> D_dep
                    wire.connect(source_subgraph.stainer.id, "output", d_dep_id, "in")

                    # D_dep -> Target Bleacher
                    wire.connect(d_dep_id, "out", target_subgraph.bleacher.id, arg_name)
                # Case B: Literal Value (Constant) - Use Probe Model
                else:
                    # 1. D_const (DataNode holding the literal value)
                    d_const_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                    d_const = PhysicsDataNode(
                        id=d_const_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
                    wire.add_node(d_const)

                    # 2. F_probe (The probe node for constants)
                    f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, arg_name)
                    f_probe = PhysicsFuncNode(
                        id=f_probe_id,
                        name=f"Probe({arg_name})",
                        input_ports={"value": PortDef("value", PortRole.DATA)},
                        output_ports={"out": PortDef("out", PortRole.DATA)},
                    )
                    wire.add_node(f_probe)

                    # 3. D_probed (Intermediate data node to connect to Bleacher)
                    d_probed_id = f"{f_probe_id}.out"
                    d_probed = PhysicsDataNode(
                        id=d_probed_id, name=f"Probed({arg_name})"
                    )
                    wire.add_node(d_probed)

                    # 4. Wiring
                    # D_const -> F_probe
                    wire.connect(d_const_id, "out", f_probe_id, "value")
                    # F_probe -> D_probed
                    wire.connect(f_probe_id, "out", d_probed_id, "in")
                    # D_probed -> Target Bleacher
                    wire.connect(
                        d_probed_id, "out", target_subgraph.bleacher.id, arg_name
                    )

            # 4.2 Sequence Dependencies (.after())
            for dep_id in node_ir.dependencies:
                if dep_id in subgraphs:
                    source_subgraph = subgraphs[dep_id]
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"

                    # Violation Fix: Insert D_seq
                    d_seq_id = f"seq.{dep_id}.to.{node_ir.id}"
                    d_seq = PhysicsDataNode(id=d_seq_id, name=f"Seq({dep_id})")
                    wire.add_node(d_seq)

                    wire.connect(source_subgraph.stainer.id, "output", d_seq_id, "in")
                    wire.connect(
                        d_seq_id, "out", target_subgraph.bleacher.id, port_name
                    )

            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                assert source_subgraph.stainer is not None

                # Violation Fix: Insert D_cond
                d_cond_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
                d_cond = PhysicsDataNode(
                    id=d_cond_id, name=f"Cond({node_ir.condition})"
                )
                wire.add_node(d_cond)

                wire.connect(source_subgraph.stainer.id, "output", d_cond_id, "in")
                wire.connect(d_cond_id, "out", target_subgraph.bleacher.id, "condition")

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name, amount in node_ir.constraints.items():
                allocator_id = PhysicalIdGenerator.global_allocator(res_name)
                req_buffer_id = f"buffer.req.{res_name}"
                rel_buffer_id = f"buffer.rel.{res_name}"

                # --- A. Request Chain ---
                # 1. D_const (Amount)
                d_amt_id = PhysicalIdGenerator.constant(
                    node_ir.id, f"req_amt_{res_name}"
                )
                d_amt = PhysicsDataNode(
                    id=d_amt_id,
                    name=f"Amt({res_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=amount,
                )
                wire.add_node(d_amt)

                # 2. F_probe (ConstProbe)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({res_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                wire.add_node(f_probe)

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
                wire.add_node(f_req)

                # 4. Wiring
                # D_amt -> F_probe
                wire.connect(d_amt_id, "out", f_probe_id, "value")

                # F_probe -> D_probed
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
                wire.add_node(d_probed)

                wire.connect(f_probe_id, "out", d_probed_id, "in")

                # D_probed -> F_req
                wire.connect(d_probed_id, "out", f_req_id, "amount")

                # F_req -> D_req_buffer (Global Buffer for the Allocator)
                wire.connect(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")

                # --- B. Grant Wiring ---
                gnt_buffer_id = f"buffer.gnt.{res_name}"
                if gnt_buffer_id not in physical_graph.nodes:
                    d_gnt_buffer = PhysicsDataNode(
                        id=gnt_buffer_id, name=f"GntBuffer({res_name})", capacity=1000
                    )
                    wire.add_node(d_gnt_buffer)

                    # Allocator -> Grant Buffer (Only once per resource)
                    wire.connect(allocator_id, PortName.GNT, gnt_buffer_id, "in")

                target_tag = f_req_id
                port_name = f"res_{res_name}"

                # Grant Buffer -> Bleacher (Filtered by Tag)
                wire.connect(
                    gnt_buffer_id,
                    "out",
                    subgraph.bleacher.id,
                    port_name,
                    tag_filter=target_tag,
                )

                # --- C. Release Wiring ---
                # Stainer -> RelBuffer
                wire.connect(
                    subgraph.stainer.id,
                    port_name,
                    rel_buffer_id,
                    "in",
                )

        # Final Validation Step (Validator still useful for global checks like Bipartite rule)
        self._validator.validate(physical_graph, graph_ir)

        return physical_graph

        # Final Validation Step
        self._validator.validate(physical_graph, graph_ir)

        return physical_graph
