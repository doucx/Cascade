import hashlib
from typing import Any, List, Dict, Tuple
from cascade.graph.model import Graph, Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing a stable Merkle hash for a node instance.
    This is the `Instance Hash`, which uniquely identifies a specific, fully-parameterized
    node instance. It is used for results caching and node de-duplication within a graph.
    """

    def compute_structural_hash(self, result: Any, dep_nodes: Dict[str, Node]) -> str:
        """
        Computes the Structural Hash (Instance Hash) for a given result object.
        """
        if isinstance(result, LazyResult):
            return self._compute_lazy_result_hash(result, dep_nodes)
        elif isinstance(result, MappedLazyResult):
            return self._compute_mapped_result_hash(result, dep_nodes)
        else:
            raise TypeError(f"Cannot compute hash for type {type(result)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _compute_lazy_result_hash(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components (Always structural)
        struct_args = self._build_hash_components(result.args, dep_nodes)
        struct_kwargs = self._build_hash_components(result.kwargs, dep_nodes)

        # 3. Metadata Components (Structural properties)
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # 4. Constraint Components (Always structural)
        struct_constraints = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            struct_constraints.append(f"Constraints({','.join(s_vals)})")

        # Assemble Structural ID
        return self._get_merkle_hash(
            base_comps
            + ["Args:"]
            + struct_args
            + ["Kwargs:"]
            + struct_kwargs
            + meta_comps
            + struct_constraints
        )

    def _compute_mapped_result_hash(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]

        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # Arguments (Always structural)
        struct_kwargs = self._build_hash_components(result.mapping_kwargs, dep_nodes)

        # Assemble
        return self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        )

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, Node]
    ) -> List[str]:
        """
        Recursively builds hash components, always including literal values.
        """
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            # The reference is always to the full structural ID of the dependency
            components.append(f"LAZY({node.structural_id})")

        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components(obj.selector, dep_nodes))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components(obj.routes[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes))
            components.append("]")

        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(self._build_hash_components(obj[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")

        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components


class BlueprintHasher:
    """
    Computes a hash for a Graph's topology, ignoring literal input values.
    This hash is used to cache compiled execution plans.
    """

    def compute_hash(self, graph: Graph) -> str:
        """Computes the blueprint hash for the entire graph."""
        all_components = []
        # Sort nodes by structural_id to ensure deterministic traversal
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.structural_id)

        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))

        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        """Gets the hash components for a single node, normalizing literals."""
        components = [f"Node({node.name}, type={node.node_type})"]

        # Policies are part of the structure
        if node.retry_policy:
            rp = node.retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if node.cache_policy:
            components.append(f"Cache({type(node.cache_policy).__name__})")

        # IMPORTANT: Normalize literal bindings
        if node.input_bindings:
            components.append("Bindings:?")

        # Dependencies are structural
        # Sort edges to ensure determinism
        incoming_edges = sorted(
            [e for e in graph.edges if e.target.structural_id == node.structural_id],
            key=lambda e: e.source.structural_id,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.structural_id}, to={node.structural_id}, type={edge.edge_type.name})"
            )

        return components
