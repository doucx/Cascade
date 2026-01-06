from typing import Any, Dict

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

from cascade.reflection import ReflectionAnalyzer


from cascade.runtime.legacy.strategies.base import ExecutionContext


class VMExecutionStrategy:
    def __init__(self, bus: Any):
        self.bus = bus
        self.analyzer = ReflectionAnalyzer()

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any:
        pass

    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        results = {}
        # Use a stack to avoid deep recursion
        stack = [target]
        processed_uuids = set()

        while stack:
            current = stack.pop()

            if isinstance(current, (LazyResult, MappedLazyResult)):
                if current._uuid in processed_uuids:
                    continue
                processed_uuids.add(current._uuid)
                results[current._uuid] = current

                # Common dependencies
                if current._condition:
                    stack.append(current._condition)
                if hasattr(current, "_dependencies"):
                    stack.extend(current._dependencies)

                # Type-specific arguments
                if isinstance(current, LazyResult):
                    stack.extend(current.args)
                    stack.extend(current.kwargs.values())
                elif isinstance(current, MappedLazyResult):
                    stack.extend(current.mapping_kwargs.values())

            elif isinstance(current, (list, tuple)):
                stack.extend(current)
            elif isinstance(current, dict):
                stack.extend(current.values())

        return results
