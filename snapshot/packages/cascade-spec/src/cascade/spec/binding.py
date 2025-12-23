from dataclasses import dataclass
from typing import Union, Any

@dataclass(frozen=True)
class Constant:
    """
    Represents a compile-time constant value that is embedded directly in the graph.
    This should be used sparingly, primarily for structural configuration that
    affects the topology itself.
    """
    value: Any

    def __repr__(self):
        return f"Const({self.value!r})"

# A Binding is typically a raw value (Any) or a wrapped Constant.
Binding = Any