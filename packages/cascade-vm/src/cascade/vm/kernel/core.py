import logging
from typing import Any, Callable, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Ref]
KernelFunc = Callable[[Dict[str, Ref], PhysicsFuncNode, ResourceRegistry], Dict[str, Ref]]


class PhysicsKernel:
    """
    The synchronous execution core for Cascade v3.1 Physics Layer.

    Responsibilities:
    1. Executes Standard Library ICs (Bleachers, Stainers, Allocators).
    2. Operates exclusively on References (Ref), never dereferencing payloads.
    3. Guarantees microseconds-level latency per operation.
    4. Purely synchronous execution model (no async/await).
    """

    def __init__(self, function_map: Dict[str, KernelFunc], resources: ResourceRegistry):
        self._function_map = function_map
        self._resources = resources

    def execute(
        self, node: PhysicsFuncNode, inputs: Dict[str, Ref]
    ) -> Dict[str, Ref]:
        """
        Execute a kernel function for the given node.

        Args:
            node: The physical function node being executed.
            inputs: A dictionary of input References mapped by port name.

        Returns:
            A dictionary of output References mapped by port name.

        Raises:
            ValueError: If no kernel function is mapped to the node.
            Exception: Any error raised by the kernel function itself.
        """
        func = self._function_map.get(node.id)
        if not func:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            raise e