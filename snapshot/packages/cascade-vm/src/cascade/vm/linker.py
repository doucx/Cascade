from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.spec.physical.triad import RetryNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough


class LinkerError(RuntimeError):
    pass


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        # Phase 1: Integrity Validation
        self._verify_integrity(assembly, registry)

        # Phase 2: Function Mapping
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            # All user workers are now implemented by the standard_dispatcher.
            if node_id in assembly.symbol_table:
                function_map[node_id] = standard_dispatcher
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map

    def _verify_integrity(self, assembly: Assembly, registry: CodeRegistry) -> None:
        missing_hashes = {
            code_hash
            for code_hash in assembly.symbol_table.values()
            if not registry.has(code_hash)
        }

        if missing_hashes:
            missing_list = "\n - ".join(sorted(list(missing_hashes)))
            raise LinkerError(
                f"Linker integrity check failed. The following code hashes "
                f"are required by the assembly but were not found in the CodeRegistry:\n"
                f" - {missing_list}"
            )

    def _resolve_stdlib(self, node_id: str) -> Optional[Callable]:
        # Triad
        if node_id.endswith(".bleach"):
            return standard_bleacher
        if node_id.endswith(".stain"):
            return standard_stainer

        # Observability
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer

        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith("req."):
            return resource_requestor
        if "gate.wakeup" in node_id:
            return gate_passthrough

        # System / Egress
        if node_id.startswith("egress."):
            return standard_egress

        return None
