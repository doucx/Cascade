import sys
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
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
            physical_graph.nodes[ledger_id] = d_ledger

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
            physical_graph.nodes[allocator_id] = f_allocator

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
            physical_graph.nodes[reclaimer_id] = f_reclaimer

            # Wiring: Ledger <-> Allocator
            physical_graph.channels.append(
                Channel(ledger_id, "out", allocator_id, PortName.LEDGER_IN)
            )
            physical_graph.channels.append(
                Channel(allocator_id, PortName.LEDGER_OUT, ledger_id, "in")
            )

            # Wiring: Ledger <-> Reclaimer
            physical_graph.channels.append(
                Channel(ledger_id, "out", reclaimer_id, PortName.LEDGER_IN)
            )
            physical_graph.channels.append(
                Channel(reclaimer_id, PortName.LEDGER_OUT, ledger_id, "in")
            )

            # Request Buffer
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )
            physical_graph.nodes[d_req_buffer_id] = d_req_buffer

            # Buffer -> Allocator
            physical_graph.channels.append(
                Channel(d_req_buffer_id, "out", allocator_id, PortName.REQ)
            )
            # Recirculation: Allocator -> Buffer
            physical_graph.channels.append(
                Channel(allocator_id, PortName.REQ_OUT, d_req_buffer_id, "in")
            )

            # Release Buffer
            # Created here instead of implicitly later to ensure consistent ID
            rel_buffer_id = f"buffer.rel.{res_def.name}"
            d_rel_buffer = PhysicsDataNode(
                id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
            )
            physical_graph.nodes[rel_buffer_id] = d_rel_buffer
            
            # Buffer -> Reclaimer
            physical_graph.channels.append(
                Channel(rel_buffer_id, "out", reclaimer_id, PortName.REL)
            )

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
        physical_graph.nodes[d_life_id] = d_life
        physical_graph.nodes[f_obs_id] = f_obs

        physical_graph.channels.append(
            Channel(
                source_node_id=d_life_id,
                source_port="out",
                target_node_id=f_obs_id,
                target_port="event_token",
            )
        )

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
            physical_graph.nodes.update(subgraph.nodes)
            physical_graph.channels.extend(subgraph.channels)

            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )

        # 4. Wire dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert target_subgraph.bleacher is not None

            # 4.1 Data Dependencies (Arguments)
            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]

                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
                # Case B: Literal Value (Constant)
                else:
                    # Create a dedicated DataNode for this constant
                    const_node_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                    const_node = PhysicsDataNode(
                        id=const_node_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
                    physical_graph.nodes[const_node_id] = const_node

                    # Wire Const -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=const_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

            # 4.2 Sequence Dependencies (.after())
            for dep_id in node_ir.dependencies:
                if dep_id in subgraphs:
                    source_subgraph = subgraphs[dep_id]
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )

            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                # Help static analysis
                assert source_subgraph.stainer is not None

                physical_graph.channels.append(
                    Channel(
                        source_node_id=source_subgraph.stainer.id,
                        source_port="output",
                        target_node_id=target_subgraph.bleacher.id,
                        target_port="condition",
                    )
                )

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

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
                physical_graph.nodes[d_amt_id] = d_amt

                # 2. F_probe (ConstProbe)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({res_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                physical_graph.nodes[f_probe_id] = f_probe

                # 3. F_req (Requestor)
                f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
                f_req = PhysicsFuncNode(
                    id=f_req_id,
                    name=f"Req({res_name})",
                    input_ports={"amount": PortDef("amount", PortRole.DATA)},
                    output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
                )
                physical_graph.nodes[f_req_id] = f_req

                # 4. Wiring: D_amt -> F_probe -> D_temp -> F_req -> D_req_buffer
                # We need intermediate data nodes because of Bipartite rule (F->D->F)
                
                # D_amt -> F_probe
                physical_graph.channels.append(
                    Channel(d_amt_id, "out", f_probe_id, "value")
                )

                # F_probe -> D_probed
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
                physical_graph.nodes[d_probed_id] = d_probed

                physical_graph.channels.append(
                    Channel(f_probe_id, "out", d_probed_id, "in")
                )
                
                # D_probed -> F_req
                physical_graph.channels.append(
                    Channel(d_probed_id, "out", f_req_id, "amount")
                )

                # F_req -> D_req_buffer (Global Buffer for the Allocator)
                physical_graph.channels.append(
                    Channel(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")
                )

                # --- B. Grant Wiring ---
                # Allocator (GNT) -> Bleacher (res_{name})
                target_tag = f_req_id
                
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=allocator_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )

                # --- C. Release Wiring ---
                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )

        return physical_graph
