import hashlib
from typing import List
from cascade.runtime.graph.model import Graph, Node


class BlueprintHasher:
    # Existing logic for Blueprint hashing
    def compute_hash(self, graph: Graph) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['canonical_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")

        # ... Edge logic remains same
        incoming_edges = sorted(
            [
                e
                for e in graph.edges
                if e.target.current_node_instance_hash
                == node.current_node_instance_hash
            ],
            key=lambda e: e.source.current_node_instance_hash,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.current_node_instance_hash}, to={node.current_node_instance_hash}, type={edge.edge_type.name})"
            )
        return components