import logging
from typing import Callable, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Ref]
KernelFunc = Callable[
    [Dict[str, Ref], PhysicsFuncNode, ResourceRegistry], Dict[str, Ref]
]


class PhysicsKernel:
    def __init__(
        self, function_map: Dict[str, KernelFunc], resources: ResourceRegistry
    ):
        self._function_map = function_map
        self._resources = resources

    def execute(self, node: PhysicsFuncNode, inputs: Dict[str, Ref]) -> Dict[str, Ref]:
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
