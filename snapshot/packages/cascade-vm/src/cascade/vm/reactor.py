from typing import List, Set, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode
from cascade.vm.memory import VolatileMemory

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(self, graph: BipartiteGraph, memory: VolatileMemory):
        self.graph = graph
        self.memory = memory

    def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.
        
        Returns:
            int: The number of nodes that fired during this step.
        """
        raise NotImplementedError

    def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. (Future) Submits the actual payload to an Executor.
        """
        raise NotImplementedError