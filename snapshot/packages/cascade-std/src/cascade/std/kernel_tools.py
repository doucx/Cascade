from functools import wraps
from typing import Dict, Any, Type, TypeVar, MutableMapping
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physics import PhysicsSpec, PortDirection

T = TypeVar("T", bound=PhysicsSpec)


class DynamicOutputMap(MutableMapping):
    """
    Proxy for writing to dynamic output ports with prefix validation.
    """
    def __init__(self, target_dict: Dict[str, Token], prefix: str):
        self._target = target_dict
        self._prefix = prefix

    def __setitem__(self, key: str, value: Token) -> None:
        if not key.startswith(self._prefix):
             raise ValueError(f"Dynamic port '{key}' does not match required prefix '{self._prefix}'")
        self._target[key] = value

    def __getitem__(self, key: str) -> Token:
        return self._target[key]

    def __delitem__(self, key: str) -> None:
        del self._target[key]

    def __iter__(self):
        return iter(self._target)

    def __len__(self):
        return len(self._target)


class IOWrapper:
    """
    A zero-copy view over the input and output dictionaries.
    Translates attribute access to dictionary lookups based on the Spec.
    Supports "Static First, Dynamic Fallback" for map ports.
    """
    __slots__ = ("_inputs", "_outputs", "_spec")

    def __init__(self, inputs: Dict[str, Token], outputs: Dict[str, Token], spec: Type[PhysicsSpec]):
        self._inputs = inputs
        self._outputs = outputs
        self._spec = spec

    def __getattr__(self, name: str) -> Any:
        # 1. Check Input Ports
        if name in self._spec.input_ports:
            port_def = self._spec.input_ports[name]
            
            # Case A: Dynamic Map Input
            if port_def.is_map:
                # Collect all inputs that are NOT associated with a static port
                static_names = {
                    p.name for p in self._spec.input_ports.values() 
                    if not p.is_map
                }
                return {
                    k: v for k, v in self._inputs.items() 
                    if k not in static_names
                }
            
            # Case B: Static Input
            port_name = port_def.name
            return self._inputs.get(port_name)
        
        # 2. Check Output Ports
        if name in self._spec.output_ports:
             port_def = self._spec.output_ports[name]
             
             # Case C: Dynamic Map Output
             if port_def.is_map:
                 return DynamicOutputMap(self._outputs, port_def.prefix)

             # Case D: Static Output (Reading back what we wrote)
             port_name = port_def.name
             return self._outputs.get(port_name)

        raise AttributeError(f"'{self._spec.__name__}' IO has no port mapping for '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inputs", "_outputs", "_spec"):
            super().__setattr__(name, value)
            return

        # Check Output Ports
        if name in self._spec.output_ports:
            port_def = self._spec.output_ports[name]
            
            # Direct assignment to a Map property is not allowed (must use item assignment)
            if port_def.is_map:
                raise AttributeError(
                    f"Cannot assign to map port '{name}' directly. Use indexing (io.{name}['key'] = val)."
                )

            port_name = port_def.name
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