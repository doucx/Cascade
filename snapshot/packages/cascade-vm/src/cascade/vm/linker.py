from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.constants import NodePrefix
from .registry import CodeRegistry

# Dyad Implementations
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander

# Common Standard Library
from cascade.std.system.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress
from cascade.std.system.gate import gate_passthrough
from cascade.std.system.time import standard_sleep


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

            # In the Dyad architecture, all physical function nodes map to a
            # standard library IC. User code is invoked by the ComputeService,
            # not linked directly into the kernel. The Linker's role is to
            # resolve the system-level ICs based on naming conventions.
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
        # Dyad Primitives
        if node_id.endswith(f".{NodePrefix.LAUNCH}"):
            return standard_launcher
        if node_id.endswith(f".{NodePrefix.LAND}"):
            return standard_lander

        # System & Time
        if node_id.endswith(f".{NodePrefix.SLEEP}"):
            return standard_sleep
        if node_id == PhysicalIdGenerator.observability_observer():
            return standard_observer
        if node_id.startswith(f"{NodePrefix.EGRESS}."):
            return standard_egress

        # Resources
        if "allocator" in node_id:
            return discrete_allocator
        if "reclaimer" in node_id:
            return discrete_reclaimer
        if node_id.startswith(f"{NodePrefix.REQ}."):
            return resource_requestor
        if f"{NodePrefix.GATE}.wakeup" in node_id:
            return gate_passthrough

        return None
