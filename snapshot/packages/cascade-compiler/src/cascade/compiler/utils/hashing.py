import hashlib
from typing import Any, List, Dict

from cascade.spec.ir.models import TaskDef
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Any],  # Values can be NodeIR (v3) or Node (v2)
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        # According to Axiom: [State]_[Source]_[Object]_hash
        # Use 'canonical' state here because it represents the stable identity used for linking.
        canonical_code_structure_hash = definition.fingerprint[
            "current_code_structure_hash"
        ]
        components = [f"CodeHash:{canonical_code_structure_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
        task_obj = getattr(result, "task", None) or getattr(result, "factory", None)
        is_pure = getattr(task_obj, "pure", False) if task_obj else False

        if not is_pure:
            # Impure tasks are instance-identity based.
            # We use the LazyResult's UUID as a salt.
            components.append(f"Salt({result._uuid})")

        # 3. Policies
        if getattr(result, "_retry_policy", None):
            rp = result._retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if getattr(result, "_cache_policy", None):
            components.append(f"Cache({type(result._cache_policy).__name__})")

        # 4. Bindings (Instance Arguments)
        if isinstance(result, MappedLazyResult):
            components.append("MapKwargs:")
            components.extend(
                self._build_hash_components(result.mapping_kwargs, dep_nodes)
            )
        else:
            components.append("Args:")
            components.extend(self._build_hash_components(result.args, dep_nodes))
            components.append("Kwargs:")
            components.extend(self._build_hash_components(result.kwargs, dep_nodes))

        # 5. Metadata
        cond = getattr(result, "_condition", None)
        if cond:
            # We need the ID of the condition node
            # Handle potential MappedLazyResult or other types in condition if necessary
            # For now assuming LazyResult or similar which is in dep_nodes
            if hasattr(cond, "_uuid") and cond._uuid in dep_nodes:
                node = dep_nodes[cond._uuid]
                node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
                components.append(f"ConditionID:{node_id}")
            else:
                components.append("Condition:UNKNOWN")

        deps = getattr(result, "_dependencies", None)
        if deps:
            components.append("Dependencies:[")
            # Sort by UUID to ensure stable hash
            sorted_deps = sorted(deps, key=lambda x: x._uuid)
            for dep in sorted_deps:
                if hasattr(dep, "_uuid") and dep._uuid in dep_nodes:
                    node = dep_nodes[dep._uuid]
                    node_id = getattr(
                        node, "id", getattr(node, "structural_id", str(node))
                    )
                    components.append(f"DepID:{node_id}")
                else:
                    components.append("DepID:UNKNOWN")
            components.append("]")

        # 6. Constraints
        constraints = getattr(result, "_constraints", None)
        if constraints:
            reqs = constraints.requirements
            keys = sorted(reqs.keys())
            s_vals = [f"{k}={reqs[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")

        return self._get_merkle_hash(components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Any]) -> List[str]:
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            # Duck-typing: Support both v3 NodeIR (id) and v2 Node (structural_id)
            node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
            components.append(f"LAZY({node_id})")

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
