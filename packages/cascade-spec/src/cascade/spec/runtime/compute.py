from typing import Protocol, Dict, Awaitable, Any
from cascade.spec.physical.object import Ref


class ComputeDelegate(Protocol):
    """
    Protocol for offloading computation to the Data Plane (User Executors).
    This interface deals exclusively with References, never with raw objects.
    """

    def submit(
        self, code_hash: str, input_refs: Dict[str, Ref], config: Dict[str, Any]
    ) -> Awaitable[Ref]:
        """
        Submit a computation task asynchronously.

        Args:
            code_hash: The canonical hash of the code to execute.
            input_refs: A dictionary mapping argument names to input References.
            config: Execution configuration (e.g., resources, timeouts).

        Returns:
            An Awaitable that resolves to a Ref pointing to the result.
            The Reactor should NOT await this directly in its main loop;
            instead, it should treat this as a signal that the task has been dispatched.
        """
        ...