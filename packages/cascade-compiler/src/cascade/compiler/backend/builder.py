from typing import Dict

from cascade.spec.ir.models import GraphIR
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from .expander import Expander, SubGraph


class Builder:
    """
    The master assembler for the physical graph.
    It takes a logical GraphIR, expands each node into a Triad,
    and then wires them together along with observability sidecars.
    """

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
                )
            )
            # F_post (end) -> D_life
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life.id,
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
                            # Note: The target port is implicitly the 'arg_name',
                            # which the Bleacher is designed to handle.
                        )
                    )

        return physical_graph