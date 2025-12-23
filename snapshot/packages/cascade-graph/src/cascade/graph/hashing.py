from typing import Any, Dict, Tuple, List
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


from cascade.spec.resource import Inject


class ShallowHasher:
    """
    Generates a stable shallow structural hash for a LazyResult.
    "Shallow" means it does NOT recursively hash nested LazyResults. Instead,
    it uses a placeholder, making the hash dependent only on the node's
    immediate properties and the structure of its inputs.
    """

    def __init__(self):
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> str:
        self._hash_components = []
        self._visit_top_level(target)
        fingerprint = "|".join(self._hash_components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _visit_top_level(self, obj: Any):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj)
        else:
            self._visit_arg(obj)

    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return

        if isinstance(obj, Router):
            self._hash_components.append("Router{")
            self._hash_components.append("Selector:")
            self._visit_arg(obj.selector)
            self._hash_components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                self._hash_components.append(f"Key({k})->")
                self._visit_arg(obj.routes[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for item in obj:
                self._visit_arg(item)
            self._hash_components.append("]")
            return

        if isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit_arg(obj[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
            return

        try:
            self._hash_components.append(repr(obj))
        except Exception:
            self._hash_components.append("<unreprable>")

    def _visit_lazy(self, lr: LazyResult):
        # Include UUID to ensure topological distinctness in GraphBuilder
        self._hash_components.append(f"UUID({lr._uuid})")
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        self._hash_components.append("Args:")
        for arg in lr.args:
            self._visit_arg(arg)

        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(lr.kwargs[k])

        if lr._condition:
            self._hash_components.append("Condition:PRESENT")
        if lr._dependencies:
            self._hash_components.append(f"Deps:{len(lr._dependencies)}")
        if lr._constraints:
             keys = sorted(lr._constraints.requirements.keys())
             self._hash_components.append(f"Constraints({','.join(keys)})")


    def _visit_mapped(self, mlr: MappedLazyResult):
        # Include UUID to ensure topological distinctness in GraphBuilder
        self._hash_components.append(f"UUID({mlr._uuid})")
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:PRESENT")
        if mlr._dependencies:
            self._hash_components.append(f"Deps:{len(mlr._dependencies)}")
        if mlr._constraints:
             keys = sorted(mlr._constraints.requirements.keys())
             self._hash_components.append(f"Constraints({','.join(keys)})")


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    """

    def __init__(self):
        # Flattened map of {canonical_node_path: {arg_name: value}}
        # path examples: "root", "root.args.0", "root.kwargs.data.selector"
        self.literals: Dict[str, Any] = {}
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> Tuple[str, Dict[str, Any]]:
        self._visit(target, path="root")

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.literals

    def _visit(self, obj: Any, path: str):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj, path)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj, path)
        elif isinstance(obj, Router):
            self._visit_router(obj, path)
        elif isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item, f"{path}[{i}]")
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k], f"{path}.{k}")
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We record a placeholder in the hash, and save the value.
            self._hash_components.append("LIT")
            self.literals[path] = obj

    def _visit_lazy(self, lr: LazyResult, path: str):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies (part of structure)
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        self._hash_components.append("Args:")
        for i, arg in enumerate(lr.args):
            self._visit(arg, f"{path}.args.{i}")

        # Kwargs
        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(lr.kwargs[k], f"{path}.kwargs.{k}")

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(lr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Kwargs (Mapped inputs)
        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(mlr.mapping_kwargs[k], f"{path}.kwargs.{k}")

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition, f"{path}.condition")

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(mlr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_router(self, router: Router, path: str):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector, f"{path}.selector")

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            # Note: Route keys (k) are structural! (e.g. "prod", "dev")
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k], f"{path}.routes.{k}")
