from typing import Any, Dict, List, cast
from dataclasses import dataclass

from cascade.spec.lazy_types import LazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR
from cascade.graph.analysis.reflection import ReflectionAnalyzer
from cascade.graph.hashing import HashingService


@dataclass
class NodeIDShim:
    """Helper to satisfy HashingService's expectation of objects with structural_id."""

    structural_id: str


class Frontend:
    """
    Compiler Frontend: Transforms user-facing LazyResults into Intermediate Representation (GraphIR).
    """

    @staticmethod
    def compile(target: Any) -> GraphIR:
        builder = _GraphBuilder()
        return builder.build(target)


class _GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, NodeIR] = {}  # Map structural_id -> NodeIR
        self.edges: List[EdgeIR] = []
        self._visited_lazy_uuids: Dict[str, str] = {}  # Map LazyResult.uuid -> structural_id

        # Services from cascade-graph (reused for stability)
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> GraphIR:
        # Currently we only support single root compilation, but the IR supports lists.
        # This will be expanded later.
        self._visit(target)
        return GraphIR(nodes=list(self.nodes.values()), edges=self.edges)

    def _visit(self, obj: Any) -> str:
        """
        Visits a LazyResult (or other objects), creating NodeIRs and EdgeIRs.
        Returns the structural_id of the visited object.
        """
        if not isinstance(obj, LazyResult):
            raise TypeError(f"Frontend currently only supports LazyResult, got {type(obj)}")

        # 1. Memoization check
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        # 2. Visit Dependencies (Post-order traversal)
        # We need to gather dependency IDs to compute the current node's hash
        dep_shims: Dict[str, NodeIDShim] = {}

        # 2.1 Args
        for i, arg in enumerate(obj.args):
            if isinstance(arg, LazyResult):
                dep_id = self._visit(arg)
                dep_shims[arg._uuid] = NodeIDShim(structural_id=dep_id)

        # 2.2 Kwargs
        for k, val in obj.kwargs.items():
            if isinstance(val, LazyResult):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(structural_id=dep_id)

        # 3. Analyze Task Definition
        # ReflectionAnalyzer generates TaskDef with 'current_code_structure_hash'
        task_def = self.analyzer.analyze(obj.task)

        # 4. Compute Structural ID
        # HashingService uses the shims to verify/link dependencies in the hash
        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        # 5. Create NodeIR
        if node_id not in self.nodes:
            # Extract Literal Inputs
            # Inputs include both literals and references to dependencies, 
            # but for NodeIR.inputs we typically store literals. 
            # Dependency edges represent the dynamic inputs.
            literal_inputs = {}
            for i, arg in enumerate(obj.args):
                if not isinstance(arg, LazyResult):
                    # We store positional args with string keys "0", "1", etc.
                    literal_inputs[str(i)] = arg
            
            for k, val in obj.kwargs.items():
                if not isinstance(val, LazyResult):
                    literal_inputs[k] = val

            node = NodeIR(
                id=node_id,
                definition=task_def,
                inputs=literal_inputs
            )
            self.nodes[node_id] = node

        # 6. Create Edges
        # Edges connect the dependencies visited in step 2 to this node
        for i, arg in enumerate(obj.args):
            if isinstance(arg, LazyResult):
                source_id = dep_shims[arg._uuid].structural_id
                self.edges.append(EdgeIR(
                    source_id=source_id,
                    target_id=node_id,
                    target_arg=str(i)
                ))

        for k, val in obj.kwargs.items():
            if isinstance(val, LazyResult):
                source_id = dep_shims[val._uuid].structural_id
                self.edges.append(EdgeIR(
                    source_id=source_id,
                    target_id=node_id,
                    target_arg=k
                ))

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id