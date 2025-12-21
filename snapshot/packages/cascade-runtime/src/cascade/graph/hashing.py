import hashlib
import json
from typing import Any, Dict, Tuple, List, Union

# We import LazyResult only for type checking to avoid circular imports at runtime if possible,
# but for logic we need isinstance checks.
# Since this module is in runtime, and lazy_types is in interfaces, it is safe to import.
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router


def _get_type_name(obj: Any) -> str:
    return type(obj).__name__


def compute_topology_hash(obj: Any) -> str:
    """
    Computes a stable hash representing the topological structure of a LazyResult.
    
    Rules:
    1. LazyResult / MappedLazyResult:
       Hash = Hash(TaskName, Hash(Args), Hash(Kwargs), Hash(Policies))
       This captures the compute graph structure.
       
    2. Router:
       Hash = Hash("Router", Hash(Selector), Hash(Routes))
       
    3. Literals (int, str, float, bool, None):
       Hash = Hash("Literal", TypeName)
       CRITICAL: The *value* is ignored. This allows step(1) and step(2) 
       to share the same topology hash.
       
    4. Collections (list, tuple, dict):
       Recursively hashed. Structure matters.
       
    Returns:
        A hex digest string.
    """
    hasher = hashlib.blake2b(digest_size=16)
    _update_hash(hasher, obj)
    return hasher.hexdigest()


def _update_hash(hasher, obj: Any):
    # 1. LazyResult
    if isinstance(obj, LazyResult):
        hasher.update(b"LazyResult")
        # Task identity
        hasher.update(obj.task.name.encode("utf-8"))
        
        # Recursively hash args structure
        hasher.update(b"Args")
        for arg in obj.args:
            _update_hash(hasher, arg)
            
        # Recursively hash kwargs structure (sorted keys)
        hasher.update(b"Kwargs")
        for k, v in sorted(obj.kwargs.items()):
            hasher.update(k.encode("utf-8"))
            _update_hash(hasher, v)
            
        # Hash Policies (Retry, Condition, etc.)
        if obj._retry_policy:
            hasher.update(b"Retry")
            # For retry, max_attempts implies structure (execution limit), 
            # but delay is runtime param. Let's include max_attempts in topology.
            hasher.update(str(obj._retry_policy.max_attempts).encode("utf-8"))
            
        if obj._condition:
            hasher.update(b"Condition")
            _update_hash(hasher, obj._condition)

    # 2. MappedLazyResult
    elif isinstance(obj, MappedLazyResult):
        hasher.update(b"MappedLazyResult")
        factory_name = getattr(obj.factory, "name", str(obj.factory))
        hasher.update(factory_name.encode("utf-8"))
        
        hasher.update(b"Kwargs")
        for k, v in sorted(obj.mapping_kwargs.items()):
            hasher.update(k.encode("utf-8"))
            _update_hash(hasher, v)

    # 3. Router
    elif isinstance(obj, Router):
        hasher.update(b"Router")
        _update_hash(hasher, obj.selector)
        for k, v in sorted(obj.routes.items()):
            # Route keys (e.g., "prod", "dev") are structural part of the router
            hasher.update(str(k).encode("utf-8"))
            _update_hash(hasher, v)

    # 4. Collections
    elif isinstance(obj, (list, tuple)):
        hasher.update(b"List")
        for item in obj:
            _update_hash(hasher, item)
            
    elif isinstance(obj, dict):
        hasher.update(b"Dict")
        for k, v in sorted(obj.items()):
            hasher.update(str(k).encode("utf-8"))
            _update_hash(hasher, v)

    # 5. Literals (The TCO Key)
    else:
        # We treat any other type as a "Literal Input Slot".
        # We assume that changing the *value* of a literal does not change the graph topology,
        # it only changes the data flowing through it.
        hasher.update(b"Literal")
        hasher.update(_get_type_name(obj).encode("utf-8"))
