from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from .expander import Expander, SubGraph


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR) -> BipartiteGraph:
        physical_graph = BipartiteGraph()

        # 1. Create the global observability sidecar node (D_life)
        d_life = PhysicsDataNode(id="global_d_life", name="LifecycleBus")
        physical_graph.nodes[d_life.id] = d_life

        # 2. Expand all logical nodes into physical subgraphs
        subgraphs: Dict[str, SubGraph] = {}
        for node_ir in graph_ir.nodes:
            subgraph = self._expander.expand_node(node_ir)
            subgraphs[node_ir.id] = subgraph

            # Add all nodes from the subgraph to the main graph
            physical_graph.nodes.update(subgraph.nodes)
            # Add all internal channels from the subgraph
            physical_graph.channels.extend(subgraph.channels)

            # 3. Wire observability sidecars for each subgraph
            # F_pre (start) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                    target_port="event_token",
                )
            )
            # F_post (end) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
                    target_port="event_token",
                )
            )

        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]
            for arg_name, source_ref in node_ir.inputs.items():
                # We only handle inter-node references here. Literals are handled later.
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]

                    # Connect: Source.Stainer -> Target.Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
        # 5.1 Identify all unique resources
        required_resources = {}
        for node_ir in graph_ir.nodes:
            for res_name, amount in node_ir.constraints.items():
                # We assume amount is int for now.
                if res_name not in required_resources:
                    required_resources[res_name] = amount
                else:
                    # In a static graph, we take the max requirement?
                    # No, constraints usually define how much I NEED.
                    # The global definition defines how much EXISTS.
                    # For now, we assume simple semaphore semantics: amount=1 means "I need 1 slot".
                    # The total capacity is defined elsewhere (e.g. environment).
                    # Here we need to Create the D_res nodes.
                    # We'll use a default capacity of 1 for test purposes if not defined.
                    pass

        # 5.2 Create and Wire D_res nodes
        # In a real system, capacities come from Environment. Here we hardcode or infer.
        # Let's assume a default capacity of 1 for any requested resource for MVP.
        for res_name in required_resources.keys():
            res_node_id = f"global_res_{res_name}"

            # Create D_res if not exists
            if res_node_id not in physical_graph.nodes:
                d_res = PhysicsDataNode(
                    id=res_node_id,
                    name=f"Resource({res_name})",
                    capacity=100,  # Large buffer
                    initial_tokens=1,  # Default concurrency limit = 1 for testing backpressure
                )
                physical_graph.nodes[res_node_id] = d_res

            # Wire each consumer
            for node_ir in graph_ir.nodes:
                if res_name in node_ir.constraints:
                    subgraph = subgraphs[node_ir.id]
                    port_name = f"res_{res_name}"

                    # 1. Acquire: D_res -> F_bleach
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=res_node_id,
                            source_port="out",
                            target_node_id=subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )

                    # 2. Release: F_stain -> D_res
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=subgraph.stainer.id,
                            source_port=port_name,
                            target_node_id=res_node_id,
                            target_port="in",
                        )
                    )

        return physical_graph
