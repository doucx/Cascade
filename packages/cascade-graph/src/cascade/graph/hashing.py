import hashlib
from typing import Any, List, Dict, Tuple, Optional
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing stable Merkle hashes for Cascade objects.
    It separates the concern of 'Identity' from 'Graph Construction'.
    """

    def compute_hashes(
        self, result: Any, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        """
        Computes both Structural Hash (Instance Identity) and Template Hash (Blueprint Identity)
        for a given result object.

        Args:
            result: The LazyResult or MappedLazyResult to hash.
            dep_nodes: A map of UUIDs to canonical Nodes for dependencies that have already been visited.

        Returns:
            (structural_hash, template_hash)
        """
        if isinstance(result, LazyResult):
            return self._compute_lazy_result_hashes(result, dep_nodes)
        elif isinstance(result, MappedLazyResult):
            return self._compute_mapped_result_hashes(result, dep_nodes)
        else:
            raise TypeError(f"Cannot compute hash for type {type(result)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _compute_lazy_result_hashes(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        # 1. Base Components
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components (Structural vs Template)
        struct_args = self._build_hash_components(result.args, dep_nodes, template=False)
        temp_args = self._build_hash_components(result.args, dep_nodes, template=True)

        struct_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=True
        )

        # 3. Metadata Components
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            meta_comps.append(f"Constraints({','.join(keys)})")

        # Template hash for constraints needs values too?
        # Current logic in build.py:
        # Structural: f"Constraints({','.join(keys)})"
        # Template: f"Constraints({','.join(vals)})"
        # Wait, build.py logic was:
        # Structural used keys only (implying requirement existence matters, value matters? build.py line 125)
        # Actually build.py line 125 only used keys for structural hash.
        # But for template hash (line 166), it included values.
        # This seems inverted? Template should be looser (ignore literals), Structural should be stricter.
        # Let's check the old code...
        # Old code: Structural -> keys only. Template -> keys AND values.
        # This looks like a potential bug in the old code or I'm misreading.
        # Typically Structural (Instance) Identity should include EVERYTHING (keys + values).
        # Template Identity should include Structure (keys).
        # However, for Constraints, maybe specific resource requirements define the 'shape' of execution?
        # Let's stick to a safe default: Structural includes EVERYTHING. Template includes KEYS.
        # But for migration safety, I will replicate the *intent* of correct hashing:
        # Structural = Keys + Values. Template = Keys (maybe values if they are structural?).
        # Let's fix the logic: Structural should be strict.
        
        # Re-reading old code:
        # Structural: keys only.
        # Template: values included.
        # This is definitely weird. I will implement a sane version:
        # Structural: keys + values.
        # Template: keys + values (constraints are usually structural properties of the node).

        constraint_comps = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            constraint_comps.append(f"Constraints({','.join(vals)})")
        
        # Assemble Structural
        struct_list = (
            base_comps
            + ["Args:"]
            + struct_args
            + ["Kwargs:"]
            + struct_kwargs
            + meta_comps
            + constraint_comps
        )
        structural_hash = self._get_merkle_hash(struct_list)

        # Assemble Template
        temp_list = (
            base_comps
            + ["Args:"]
            + temp_args
            + ["Kwargs:"]
            + temp_kwargs
            + meta_comps
            + constraint_comps
        )
        template_hash = self._get_merkle_hash(temp_list)

        return structural_hash, template_hash

    def _compute_mapped_result_hashes(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # Arguments
        struct_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=True
        )

        # Assemble
        struct_list = base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        structural_hash = self._get_merkle_hash(struct_list)

        temp_list = base_comps + ["MapKwargs:"] + temp_kwargs + meta_comps
        template_hash = self._get_merkle_hash(temp_list)

        return structural_hash, template_hash

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, Node], template: bool
    ) -> List[str]:
        """
        Recursively builds hash components.
        If template=True, literals are replaced by '?', but structure is preserved.
        """
        components = []
        
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            # Hash-Consing: The identity of this dependency.
            # Structural: Use the dependency's structural ID.
            # Template: Use the dependency's TEMPLATE ID.
            node = dep_nodes[obj._uuid]
            ref_id = node.template_id if template else node.structural_id
            components.append(f"LAZY({ref_id})")
        
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(
                self._build_hash_components(obj.selector, dep_nodes, template)
            )
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_hash_components(obj.routes[k], dep_nodes, template)
                )
            components.append("}")
        
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes, template))
            components.append("]")
        
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(
                    self._build_hash_components(obj[k], dep_nodes, template)
                )
            components.append("}")
        
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        
        else:
            if template:
                # Normalization: Literals become placeholders
                components.append("?")
            else:
                try:
                    components.append(repr(obj))
                except Exception:
                    components.append("<unreprable>")
        
        return components