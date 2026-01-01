import inspect
from typing import Any, Dict, Callable

from cascade.spec.physics import FuncNode, Token
from cascade.vm.reactor.events import ExecutionFinished

# A stand-in for the Reactor protocol for type hinting
ReactorProtocol = Any


class PhysicsExecutor:
    """
    A native executor for the physics-based VM. It links a FuncNode from the
    topology to a concrete Python function via the symbol table and executes it.
    """

    def __init__(self, reactor: ReactorProtocol, symbol_table: Dict[str, Callable]):
        self._reactor = reactor
        self._symbol_table = symbol_table

    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """
        Executes the logic for a given FuncNode and reports the result back
        to the reactor.
        """
        print(f"[Executor] Submitting node '{node.name}' for execution.")
        outputs = {}
        error = None

        try:
            # 1. Linking: Use the canonical code structure hash to find the executable logic.
            # This decouples the node's human-readable 'name' from its functional identity.
            func = self._symbol_table.get(node.canonical_code_structure_hash)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    f"(hash: {node.canonical_code_structure_hash}) not found in symbol table."
                )

            # 2. Unpack Payloads: Convert Dict[str, Token] to Dict[str, Any]
            kwargs = {name: token.payload for name, token in inputs.items()}

            # 3. Execution
            if node.is_map:
                # Vectorized Execution (Map)
                # 1. Determine lengths and extract iterables
                iterables = {k: v for k, v in kwargs.items() if isinstance(v, list)}
                constants = {k: v for k, v in kwargs.items() if not isinstance(v, list)}
                
                if not iterables:
                    # If nothing is a list, map behaves like a regular call returning a list
                    result = [func(**kwargs)]
                else:
                    first_len = len(next(iter(iterables.values())))
                    results = []
                    for i in range(first_len):
                        call_kwargs = constants.copy()
                        for k, v_list in iterables.items():
                            call_kwargs[k] = v_list[i]
                        
                        r = func(**call_kwargs)
                        results.append(r)
                    
                    # Handle async items in results if necessary
                    if inspect.iscoroutinefunction(func):
                        result = await asyncio.gather(*results)
                    else:
                        result = results
            else:
                # Scalar Execution
                result = func(**kwargs)
                if inspect.isawaitable(result):
                    result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
            # For now, we assume a single 'result' output port with 'default' tag.
            outputs["result"] = Token(payload=result, tag="default")
            print(f"[Executor] Node '{node.name}' execution finished successfully.")

        except Exception as e:
            error = e
            print(f"[Executor] Node '{node.name}' execution FAILED with error: {e}")

        # 5. Report: Push an ExecutionFinished event to the reactor.
        event = ExecutionFinished(node=node, outputs=outputs, error=error)
        self._reactor.push_event(event)
