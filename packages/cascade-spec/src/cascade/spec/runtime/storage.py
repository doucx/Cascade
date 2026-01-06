from typing import Protocol, Any, Dict, Optional
from cascade.spec.physical.object import Ref


class ObjectStore(Protocol):
    """
    Protocol defining the interface for the Data Plane storage layer.
    """

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        """
        Store an object and return a physical Reference.
        """
        ...

    def get(self, ref: Ref) -> Any:
        """
        Dereference a Reference to retrieve the actual object.
        This is typically an I/O intensive operation.
        """
        ...

    def peek(self, ref: Ref) -> Ref:
        """
        Retrieve the latest metadata for a Reference without loading the object.
        Useful for control flow decisions based on metadata (e.g. is_error, type checks).
        Returns a new Ref instance with potentially updated metadata.
        """
        ...

    def delete(self, ref: Ref) -> None:
        """
        Physically destroy the object associated with the Reference.
        """
        ...