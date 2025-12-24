import hashlib
from typing import Any, List, Dict, Tuple
from cascade.graph.model import Node
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
