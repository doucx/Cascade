import uuid
from typing import Any, Dict, Optional, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.storage import ObjectStore


class InMemoryObjectStore:
    """
    A reference implementation of ObjectStore using an in-memory dictionary.
    Suitable for development, testing, and single-process execution.
    URI Scheme: mem://<uuid>
    """

    def __init__(self):
        # Storage: uri -> (obj, metadata)
        self._store: Dict[str, Tuple[Any, Dict[str, Any]]] = {}

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        """
        Store an object in memory and return a Reference.
        """
        # 1. Generate URI
        uid = str(uuid.uuid4())
        uri = f"mem://{uid}"

        # 2. Prepare Metadata
        meta = metadata.copy() if metadata else {}
        
        # Auto-detect basic metadata if not provided
        if "type" not in meta:
            meta["type"] = type(obj).__name__
        
        # 3. Store
        self._store[uri] = (obj, meta)

        # 4. Return Ref
        return Ref(uri=uri, meta=meta)

    def get(self, ref: Ref) -> Any:
        """
        Dereference a Reference to retrieve the actual object.
        """
        if ref.uri not in self._store:
            raise KeyError(f"Object not found: {ref.uri}")
        
        obj, _ = self._store[ref.uri]
        return obj

    def peek(self, ref: Ref) -> Ref:
        """
        Retrieve the latest metadata for a Reference.
        For InMemoryStore, this is a cheap lookup.
        """
        if ref.uri not in self._store:
            # If the object is missing in the store but we have a Ref, 
            # we consider it "gone" or invalid, but peek typically shouldn't fail hard 
            # if we just want to check existence, or maybe it should?
            # Following the protocol: if we can't find it, we can't refresh metadata.
            # We raise KeyError to be consistent with get().
            raise KeyError(f"Object not found: {ref.uri}")

        _, meta = self._store[ref.uri]
        
        # Return a new Ref with potentially updated metadata from the store
        return Ref(uri=ref.uri, meta=meta)

    def delete(self, ref: Ref) -> None:
        """
        Physically destroy the object.
        """
        if ref.uri in self._store:
            del self._store[ref.uri]