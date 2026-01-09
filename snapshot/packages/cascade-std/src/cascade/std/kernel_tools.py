from functools import wraps
from typing import Dict, Any, Type, TypeVar
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physics import PhysicsSpec

T = TypeVar("T", bound=PhysicsSpec)


class IOWrapper:
    """
    A zero-copy view over the input and output dictionaries.
    Translates attribute access to dictionary lookups based on the Spec.
    """
    __slots__ = ("_inputs", "_outputs", "_spec")

    def __init__(self, inputs: Dict[str, Token], outputs: Dict[str, Token], spec: Type[PhysicsSpec]):
        self._inputs = inputs
        self._outputs = outputs
        self._spec = spec

    def __getattr__(self, name: str) -> Any:
        # 1. Check Input Ports
        if name in self._spec.input_ports:
            port_name = self._spec.input_ports[name].name
            # If the port is not in inputs, it means no token arrived (optional input).
            # We return None in that case, or raise? For now, None seems safer for "Gate" logic.
            return self._inputs.get(port_name)
        
        # 2. Check Output Ports (for reading back what we wrote? Uncommon but possible)
        if name in self._spec.output_ports:
             port_name = self._spec.output_ports[name].name
             return self._outputs.get(port_name)

        raise AttributeError(f"'{self._spec.__name__}' IO has no port mapping for '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inputs", "_outputs", "_spec"):
            super().__setattr__(name, value)
            return

        # Check Output Ports
        if name in self._spec.output_ports:
            port_name = self._spec.output_ports[name].name
            self._outputs[port_name] = value
            return

        raise AttributeError(f"'{self._spec.__name__}' IO has no output port mapping for '{name}'")


def implements(spec: Type[PhysicsSpec]):
    """
    Decorator that adapts a kernel function to use the typed IO interface.
    
    Transforms:
        def my_kernel(inputs, node, resources) -> Dict
    Into:
        def my_kernel(io, node, resources) -> None
        
    The wrapper handles the creation of the outputs dictionary and returns it.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(inputs: Dict[str, Token], node: PhysicsNode, resources: Any) -> Dict[str, Token]:
            outputs: Dict[str, Token] = {}
            io = IOWrapper(inputs, outputs, spec)
            
            # Call the inner function. It is expected to set attributes on 'io' (populating 'outputs')
            # and return None.
            func(io, node, resources)
            
            return outputs
        
        # Attach spec metadata for introspection/docs
        wrapper.__spec__ = spec
        return wrapper
    return decorator