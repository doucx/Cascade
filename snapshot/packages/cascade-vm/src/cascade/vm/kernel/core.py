from __future__ import annotations

import logging
from typing import Callable, Dict

from cascade.spec.physical.nodes import PhysicsFuncNode, Token

from ..resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Token], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Token]
KernelFunc = Callable[
    [Dict[str, Token], PhysicsFuncNode, ResourceRegistry], Dict[str, Token]
]


class PhysicsKernel:
    def __init__(
        self, function_map: dict[str, KernelFunc], resources: ResourceRegistry
    ):
        self._function_map = function_map
        self._resources = resources

    def execute(
        self, node: PhysicsFuncNode, inputs: dict[str, Token]
    ) -> dict[str, Token]:
        func = self._function_map.get(node.id)
        if not func:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            raise
