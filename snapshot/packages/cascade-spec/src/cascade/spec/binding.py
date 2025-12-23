from dataclasses import dataclass
from typing import Union, Any

@dataclass(frozen=True)
class SlotRef:
    """
    Represents a reference to a value stored in a separate data tuple.
    Used by Nodes to point to their runtime arguments without holding the data.
    """
    index: int

    def __repr__(self):
        return f"Slot({self.index})"

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

# A Binding is either a reference to a runtime slot or a static constant.
Binding = Union[SlotRef, Constant]