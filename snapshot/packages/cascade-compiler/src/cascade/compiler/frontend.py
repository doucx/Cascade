from typing import Any, Dict, List, cast
from dataclasses import dataclass

from typing import Any, Dict, List, cast, Callable
from dataclasses import dataclass

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.compiler_result import CompilationResult
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
    def compile(target: Any) -> CompilationResult:
        builder = _GraphBuilder()
        return builder.build(target)


class _GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, NodeIR] = {}  # Map structural_id -> NodeIR
        self.edges: List[EdgeIR] = []
        self.symbol_table: Dict[str, Callable] = {}
        self._visited_lazy_uuids: Dict[str, str] = {}  # Map LazyResult.uuid -> structural_id

        # Services from cascade-graph (reused for stability)
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> CompilationResult:
        self._visit(target)
        graph = GraphIR(nodes=list(self.nodes.values()), edges=self.edges)
        return CompilationResult(ir=graph, symbol_table=self.symbol_table)

    def _visit(self, obj: Any) -> str:
        """
        Visits a LazyResult type, creating NodeIRs and EdgeIRs.
        Returns the structural_id of the visited object.
        """
        if isinstance(obj, MappedLazyResult):
            return self._visit_mapped_result(obj)
        elif isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
        else:
            raise TypeError(f"Frontend currently only supports LazyResult types, got {type(obj)}")

    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(arg)
                dep_shims[arg._uuid] = NodeIDShim(structural_id=dep_id)

        for val in obj.kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(structural_id=dep_id)
        
        if obj._condition:
            if isinstance(obj._condition, LazyResult):
                dep_id = self._visit(obj._condition)
                dep_shims[obj._condition._uuid] = NodeIDShim(structural_id=dep_id)

        task_def = self.analyzer.analyze(obj.task)
        
        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]
        self.symbol_table[code_hash] = obj.task.func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            literal_kwargs = {
                k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }

            node = NodeIR(id=node_id, definition=task_def, args=literal_args, kwargs=literal_kwargs)
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[arg._uuid].structural_id,
                    target_id=node_id,
                    target_arg=str(i)
                ))

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))
        
        if obj._condition:
            self.edges.append(EdgeIR(
                source_id=dep_shims[obj._condition._uuid].structural_id,
                target_id=node_id,
                target_arg="_condition",
                kind=EdgeKind.CONTROL
            ))

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id

    def _visit_mapped_result(self, obj: MappedLazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}
        for val in obj.mapping_kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                dep_id = self._visit(val)
                dep_shims[val._uuid] = NodeIDShim(structural_id=dep_id)

        task_def = self.analyzer.analyze(obj.factory)

        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]
        
        # Ensure we store the raw function, not the Task wrapper
        # The analyzer usually handles extraction, but we need the raw callable for VM
        func = obj.factory
        if hasattr(func, "func"): # Unwrap Task objects
            func = func.func
            
        self.symbol_table[code_hash] = func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
            literal_kwargs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                kwargs=literal_kwargs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))

        self._visited_lazy_uuids[obj._uuid] = node_id
        return node_id