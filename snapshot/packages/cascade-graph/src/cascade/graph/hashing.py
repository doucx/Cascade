from typing import Any, Dict, Tuple, List, Set
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    
    It uses a deterministic DFS traversal to assign a 'structural_id' to each
    unique LazyResult node. The returned literals are keyed by this ID.
    """

    def __init__(self):
        # Map of {structural_id: {arg_name: value}}
        self.literals: Dict[int, Dict[str, Any]] = {}
        self._hash_components: List[str] = []
        
        # DAG support: track visited objects by their id()
        # Maps id(obj) -> structural_id
        self._visited: Dict[int, int] = {}
        self._counter = 0

    def hash(self, target: Any) -> Tuple[str, Dict[int, Dict[str, Any]]]:
        self._visit(target)

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.literals

    def _get_next_id(self) -> int:
        sid = self._counter
        self._counter += 1
        return sid

    def _visit(self, obj: Any, role: str = ""):
        # If this is a complex node (LazyResult/Router), check DAG cache
        if isinstance(obj, (LazyResult, MappedLazyResult, Router)):
            if id(obj) in self._visited:
                # Already visited, record reference to its ID to capture topology
                sid = self._visited[id(obj)]
                self._hash_components.append(f"Ref({sid})")
                return
            
            # New node: assign ID
            sid = self._get_next_id()
            self._visited[id(obj)] = sid
            self._hash_components.append(f"Node({sid}):{role}")
            
            # Initialize literal storage for this node
            self.literals[sid] = {}
            
            # Dispatch based on type
            if isinstance(obj, LazyResult):
                self._visit_lazy(obj, sid)
            elif isinstance(obj, MappedLazyResult):
                self._visit_mapped(obj, sid)
            elif isinstance(obj, Router):
                self._visit_router(obj, sid)
            return

        # Container types pass-through (recursion)
        if isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item)
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k])
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We assume it belongs to the *current* context.
            # However, _visit is recursive. To map literals to the correct Node,
            # we need context. But wait, `literals` dict is populated inside 
            # _visit_lazy/_visit_mapped which know their `sid`.
            # If we encounter a literal here, it means it's nested in a list/dict 
            # structure *outside* of a Node context? 
            # Actually, _visit_lazy calls _scan_args which handles literals.
            # This generic _visit is mostly for structural containers.
            
            # If we reach here with a primitive, it's structure-level data (like list content)
            # but usually args are handled specifically.
            self._hash_components.append("LIT")
            # We don't save it to self.literals here because we don't know the 'key'.
            # The caller (_scan_args) handles the saving.
            pass

    def _visit_lazy(self, lr: LazyResult, sid: int):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        for i, arg in enumerate(lr.args):
            self._scan_arg(sid, str(i), arg)

        # Kwargs
        for k in sorted(lr.kwargs.keys()):
            self._scan_arg(sid, k, lr.kwargs[k])

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition)

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for dep in lr._dependencies:
                self._visit(dep)

    def _visit_mapped(self, mlr: MappedLazyResult, sid: int):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Mapping Kwargs
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._scan_arg(sid, k, mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition)

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for dep in mlr._dependencies:
                self._visit(dep)

    def _visit_router(self, router: Router, sid: int):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector)

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k])

    def _scan_arg(self, sid: int, key: str, value: Any):
        """Helper to process an argument: either record it as literal or visit it as structure."""
        if isinstance(value, (LazyResult, MappedLazyResult, Router)):
            self._visit(value)
        elif isinstance(value, (list, tuple, dict)):
            # For containers, we must recurse to check for nested LazyResults.
            # But the container itself is also "literal structure". 
            # This is tricky. Simplified approach:
            # We only treat TOP-LEVEL primitives as literals for now in this version?
            # Or we recurse? 
            # Existing Hash logic mixed structure and data. 
            # Here we assume: if it contains LazyResult, it's structure. If not, it's literal.
            # For this phase, let's keep it simple: We treat containers as structure in Hash,
            # but we also need to extract the values if they are literals.
            
            # Let's delegate to _visit which handles recursion.
            # But how to capture the value if it's purely literal?
            # We record it in literals[sid][key] = value, BUT use a placeholder in hash?
            
            # Optimization: If the value is "simple" (JSON serializable + no LazyResult),
            # we treat it as a Literal.
            if self._is_pure_literal(value):
                self._hash_components.append("LIT")
                self.literals[sid][key] = value
            else:
                # It's mixed. We recurse.
                # This means the list/dict structure becomes part of the hash graph.
                self._visit(value)
        else:
            # Primitive Literal
            self._hash_components.append("LIT")
            self.literals[sid][key] = value

    def _is_pure_literal(self, obj: Any) -> bool:
        """Deep check if obj contains any Lazy types."""
        if isinstance(obj, (LazyResult, MappedLazyResult, Router)):
            return False
        if isinstance(obj, (list, tuple)):
            return all(self._is_pure_literal(x) for x in obj)
        if isinstance(obj, dict):
            return all(self._is_pure_literal(v) for v in obj.values())
        return True