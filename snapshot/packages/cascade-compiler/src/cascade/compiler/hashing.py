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
        dep_nodes: Dict[str, Any],  # Changed from Node to Any to break import cycle
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
        task_obj = getattr(result, "task", None) or getattr(result, "factory", None)
        is_pure = getattr(task_obj, "pure", False) if task_obj else False

        if not is_pure:
            # Impure tasks are instance-identity based.
            # We use the LazyResult's UUID as a salt.
            components.append(f"Salt({result._uuid})")

        # 3. Policies
        if result._retry_policy:
            rp = result._retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
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
        if result._condition:
            components.append("Condition:PRESENT")

        # 6. Constraints
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")

        return self._get_merkle_hash(components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Any]) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.current_node_instance_hash})")

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
    # Existing logic for Blueprint hashing (can be updated later if needed)
    def compute_hash(self, graph: Any) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Any, graph: Any) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})"
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
