import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.compute import ComputeDelegate
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry


class LocalComputeDelegate(ComputeDelegate):
    """
    A local implementation of ComputeDelegate that executes code in the current process.
    It handles:
    1. Dereferencing input Refs using the ObjectStore.
    2. Resolving code from the CodeRegistry.
    3. Executing the code (sync code in a thread pool, async code directly).
    4. Storing the result back to the ObjectStore and returning a Ref.
    """

    def __init__(
        self, store: ObjectStore, registry: CodeRegistry, max_workers: int = None
    ):
        self.store = store
        self.registry = registry
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )

    async def submit(
        self, code_hash: str, input_refs: Dict[str, Ref], config: Dict[str, Any]
    ) -> Ref:
        """
        Execute a task defined by code_hash and input_refs.
        """
        # 1. Resolve Inputs (IO Bound)
        # In a real distributed system, this might be parallelized pre-fetching.
        inputs: Dict[str, Any] = {}
        for key, ref in input_refs.items():
            inputs[key] = self.store.get(ref)

        # 2. Reconstruct Arguments (CPU Bound)
        args, kwargs = self._resolve_arguments(inputs)

        # 3. Resolve Code
        func = self.registry.get(code_hash)

        # 4. Execute (CPU/IO Mixed)
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            # Wrap exception to store it as a result?
            # Or let it propagate?
            # In v3.1, exceptions are typically values.
            # But here we might want to let the caller handle the crash
            # or return a specific Error object.
            # For simplicity in this phase, we treat the exception as the result
            # if the architecture expects 'Ref to Error'.
            # However, standard Python behavior is to raise.
            # Let's propagate for now, the caller (Reactor/Adapter) can catch.
            raise e

        # 5. Store Result (IO Bound)
        result_ref = self.store.put(result)
        return result_ref

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Reconstruct positional and keyword arguments from a flat dictionary.
        Keys that are digit strings ('0', '1') are treated as positional indices.
        Other keys are treated as keyword arguments.
        """
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        # Convert args_map to list, assuming contiguous 0-based indexing for simplicity.
        # If there are gaps, we might need a more robust approach, but Compiler guarantees 0..N.
        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs