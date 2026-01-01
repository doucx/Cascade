import sys
from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from .expander import Expander, SubGraph


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = f"global_res_{res_def.name}"
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res

        # 2. Create and wire the global observability sidecar infrastructure
        d_life_id = "global_d_life"
        f_obs_id = "global_f_obs"

        # Capacity set to maxsize to prevent backpressure from observability
        d_life = PhysicsDataNode(
            id=d_life_id, name="LifecycleBus", capacity=sys.maxsize
        )
        f_obs = ObservabilityNode(
            id=f_obs_id,
            name="LifecycleObserver",
            input_ports={"event_token": "Event"},
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

        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert target_subgraph.bleacher is not None

            for arg_name, source_ref in node_ir.inputs.items():
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

        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]
            
            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name in node_ir.constraints:
                res_node_id = f"global_res_{res_name}"
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

        return physical_graph
