import asyncio
from typing import Dict, Callable, Any, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# Helper to wrap user functions
def _make_worker_wrapper(func: Callable) -> Callable:
    async def _wrapper(
        inputs: Dict[str, Token], node: Any, resources: Any
    ) -> Dict[str, Token]:
        # Unpack inputs. The Bleacher put them in 'worker_input'
        # payload is the dict of {arg_name: val}
        if "worker_input" not in inputs:
            # Fallback or error? For now assume it's there.
            return {}

        kwargs = inputs["worker_input"].payload

        # Execute
        if asyncio.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = func(**kwargs)

        return {"worker_result": Token(payload=result)}

    return _wrapper


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            if node_id in assembly.symbol_table:
                canonical_hash = assembly.symbol_table[node_id]
                try:
                    raw_func = registry.get(canonical_hash)
                    function_map[node_id] = _make_worker_wrapper(raw_func)
                except KeyError:
                    # TODO: In distributed mode, this might trigger a code fetch
                    raise ImportError(
                        f"Failed to link node '{node_id}': Code hash '{canonical_hash}' not found in registry."
                    )
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

            # If we reach here, we have an unlinked function node.
            # In strict mode, this should probably raise.
            # For now, we leave it unmapped (Reactor will raise if it tries to execute it).

        return function_map

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

        # Probes
        if node_id.startswith("probe.const."):
            return const_probe

        return None
