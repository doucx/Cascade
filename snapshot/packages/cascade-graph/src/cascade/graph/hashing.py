import hashlib
from typing import Any, List, Dict, Tuple, Optional
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing stable Merkle hashes for Cascade objects.

    FORMAL HASHING SEMANTICS (The Hashing Manifest):
    
    1. Structural Hash (Instance Identity):
       - Purpose: Uniquely identify a specific, fully-parameterized node instance.
       - Use Case: Key for results caching (e.g., in Redis).
       - Logic: Includes task ID, policies, and ALL literal values for arguments and constraints.

    2. Template Hash (Blueprint Identity):
       - Purpose: Identify a reusable computation "blueprint" or "structure".
       - Use Case: Key for JIT compilation cache (ExecutionPlan reuse).
       - Logic: Includes task ID and structural keys, but normalizes all literal values 
                (arguments and constraint amounts) to a placeholder '?'.
    """

    def compute_hashes(
        self, result: Any, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        """
        Computes both Structural Hash and Template Hash for a given result object.
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
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components
        struct_args = self._build_hash_components(result.args, dep_nodes, template=False)
        temp_args = self._build_hash_components(result.args, dep_nodes, template=True)

        struct_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=True
        )

        # 3. Metadata Components (Structural properties)
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # 4. Constraint Components (Differentiated)
        struct_constraints = []
        temp_constraints = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            
            # Structural: Exact resource amounts
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            struct_constraints.append(f"Constraints({','.join(s_vals)})")
            
            # Template: Normalized amounts for JIT reuse
            t_vals = [f"{k}=?" for k in keys]
            temp_constraints.append(f"Constraints({','.join(t_vals)})")
        
        # Assemble Structural ID
        structural_hash = self._get_merkle_hash(
            base_comps + ["Args:"] + struct_args + ["Kwargs:"] + struct_kwargs 
            + meta_comps + struct_constraints
        )

        # Assemble Template ID
        template_hash = self._get_merkle_hash(
            base_comps + ["Args:"] + temp_args + ["Kwargs:"] + temp_kwargs 
            + meta_comps + temp_constraints
        )

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
        structural_hash = self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        )
        template_hash = self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + temp_kwargs + meta_comps
        )

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
            node = dep_nodes[obj._uuid]
            # Use appropriate ID depending on the hashing goal
            ref_id = node.template_id if template else node.structural_id
            components.append(f"LAZY({ref_id})")
        
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components(obj.selector, dep_nodes, template))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components(obj.routes[k], dep_nodes, template))
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
                components.extend(self._build_hash_components(obj[k], dep_nodes, template))
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