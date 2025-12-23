from typing import Any, Dict, Tuple, List
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class ShallowHasher:
    """
    Generates a stable shallow structural hash for a LazyResult.
    "Shallow" means it does NOT recursively hash nested LazyResults.
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
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
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
    Generates a stable structural hash for a LazyResult tree.
    Uses Python's native tuple hashing for high performance.
    """

    def __init__(self):
        # We don't need state for tuple hashing, but keeping API consistent
        pass

    def hash(self, target: Any) -> Tuple[int, None]:
        # Returns (hash_int, None). The second element is legacy 'literals' dict
        # which we don't extract during hashing anymore for speed.
        structure = self._visit(target)
        return hash(structure), None

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            return self._visit_mapped(obj)
        elif isinstance(obj, Router):
            return self._visit_router(obj)
        elif isinstance(obj, (list, tuple)):
            return tuple(self._visit(item) for item in obj)
        elif isinstance(obj, dict):
            # Sort keys for stability
            return tuple((k, self._visit(obj[k])) for k in sorted(obj.keys()))
        elif isinstance(obj, Inject):
            return ("Inject", obj.resource_name)
        else:
            # Literal value marker. We don't include the value itself in the hash
            # if we want strictly structural hashing, BUT:
            # For template matching, structure includes "where the data slots are".
            # The value itself effectively becomes a "Slot" in the template.
            # So "LIT" is correct.
            return "LIT"

    def _visit_lazy(self, lr: LazyResult) -> Tuple:
        components = ["Task", getattr(lr.task, "name", "unknown")]

        if lr._retry_policy:
            rp = lr._retry_policy
            components.append(("Retry", rp.max_attempts, rp.delay, rp.backoff))
        if lr._cache_policy:
            components.append(("Cache", type(lr._cache_policy).__name__))

        # Args
        args_tuple = tuple(self._visit(arg) for arg in lr.args)
        components.append(args_tuple)

        # Kwargs
        kwargs_tuple = tuple(
            (k, self._visit(v)) for k, v in sorted(lr.kwargs.items())
        )
        components.append(kwargs_tuple)

        if lr._condition:
            components.append(("Condition", self._visit(lr._condition)))

        if lr._dependencies:
            deps_tuple = tuple(self._visit(dep) for dep in lr._dependencies)
            components.append(("Deps", deps_tuple))

        if lr._constraints:
             # Just hash keys of constraints, values are data
             keys = tuple(sorted(lr._constraints.requirements.keys()))
             components.append(("Constraints", keys))

        return tuple(components)

    def _visit_mapped(self, mlr: MappedLazyResult) -> Tuple:
        components = ["Map", getattr(mlr.factory, "name", "unknown")]

        # MapKwargs
        kwargs_tuple = tuple(
            (k, self._visit(v)) for k, v in sorted(mlr.mapping_kwargs.items())
        )
        components.append(kwargs_tuple)

        if mlr._condition:
             components.append(("Condition", self._visit(mlr._condition)))
        if mlr._dependencies:
             deps_tuple = tuple(self._visit(dep) for dep in mlr._dependencies)
             components.append(("Deps", deps_tuple))
        if mlr._constraints:
             keys = tuple(sorted(mlr._constraints.requirements.keys()))
             components.append(("Constraints", keys))
        
        return tuple(components)

    def _visit_router(self, router: Router) -> Tuple:
        # Selector structure
        selector_struct = self._visit(router.selector)
        
        # Routes structure
        routes_items = []
        for k in sorted(router.routes.keys()):
            # Route keys are structural
            routes_items.append((k, self._visit(router.routes[k])))
        
        return ("Router", selector_struct, tuple(routes_items))