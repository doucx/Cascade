import sys
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Global Infrastructure
        # 1.1 Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = PhysicalIdGenerator.global_resource(res_def.name)
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 1.2 Global Start Pulse
        start_pulse_id = PhysicalIdGenerator.start_pulse()
        d_start = PhysicsDataNode(
            id=start_pulse_id,
            name="GlobalStartPulse",
            capacity=sys.maxsize, # Can trigger infinite source nodes
            initial_tokens=1,
        )
        physical_graph.nodes[start_pulse_id] = d_start


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

                    # Create intermediate DataNode for data transfer
                    data_node_id = f"data.{source_ref}.to.{node_ir.id}.{arg_name}"
                    data_node = PhysicsDataNode(
                        id=data_node_id,
                        name=f"Data({source_ref}->{node_ir.name}.{arg_name})",
                        capacity=1
                    )
                    physical_graph.nodes[data_node_id] = data_node

                    # Wire Stainer -> DataNode
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=data_node_id,
                            target_port="in",
                        )
                    )

                    # Wire DataNode -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=data_node_id,
                            source_port="out",
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
                    
                    # Create intermediate DataNode for the signal
                    signal_node_id = f"signal.{dep_id}.to.{node_ir.id}"
                    signal_node = PhysicsDataNode(
                        id=signal_node_id,
                        name=f"Signal({dep_id}->{node_ir.name})",
                        capacity=1
                    )
                    physical_graph.nodes[signal_node_id] = signal_node

                    # Wire Stainer -> Signal
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=signal_node_id,
                            target_port="in",
                        )
                    )
                    
                    # Wire Signal -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=signal_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )
            
            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                # Help static analysis
                assert source_subgraph.stainer is not None

                # Create intermediate DataNode for the condition signal
                cond_node_id = f"cond.{node_ir.condition}.to.{node_ir.id}"
                cond_node = PhysicsDataNode(
                    id=cond_node_id,
                    name=f"Cond({node_ir.condition}->{node_ir.name})",
                    capacity=1
                )
                physical_graph.nodes[cond_node_id] = cond_node

                # Wire Stainer -> CondNode
                physical_graph.channels.append(
                    Channel(
                        source_node_id=source_subgraph.stainer.id,
                        source_port="output",
                        target_node_id=cond_node_id,
                        target_port="in",
                    )
                )

                # Wire CondNode -> Bleacher
                physical_graph.channels.append(
                    Channel(
                        source_node_id=cond_node_id,
                        source_port="out",
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

            for res_name in node_ir.constraints:
                res_node_id = PhysicalIdGenerator.global_resource(res_name)
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
                physical_graph.channels.append(
                    Channel(
                        source_node_id=res_node_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                    )
                )

                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )

        # 6. Wire Global Start Pulse to all Source Nodes
        # A source node's bleacher is one that does not depend on any other task's stainer.
        task_fed_bleacher_ids = {
            c.target_node_id
            for c in physical_graph.channels
            if c.source_node_id.endswith(".stain")
        }

        for subgraph in subgraphs.values():
            bleacher = subgraph.bleacher
            if bleacher and bleacher.id not in task_fed_bleacher_ids:
                # This bleacher is a source node, connect it to the start pulse
                physical_graph.channels.append(
                    Channel(
                        source_node_id=start_pulse_id,
                        source_port="out",
                        target_node_id=bleacher.id,
                        target_port="__start__",
                    )
                )


        return physical_graph
