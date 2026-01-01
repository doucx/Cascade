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
        outputs = {}
        error = None

        try:
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )

            # 2. Unpack Payloads: Convert Dict[str, Token] to Dict[str, Any]
            kwargs = {name: token.payload for name, token in inputs.items()}

            # 3. Execution
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
            # For now, we assume a single 'result' output port with 'default' tag.
            outputs["result"] = Token(payload=result, tag="default")

        except Exception as e:
            error = e

        # 5. Report: Push an ExecutionFinished event to the reactor.
        event = ExecutionFinished(node=node, outputs=outputs, error=error)
        self._reactor.push_event(event)
