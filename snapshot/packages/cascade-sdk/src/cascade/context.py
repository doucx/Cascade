from typing import Dict, List, Any
from cascade.spec.input import InputSpec

class CascadeContext:
    def __init__(self):
        self._specs: Dict[str, InputSpec] = {}

    def register(self, spec: InputSpec):
        self._specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self._specs.values())

# Global singleton for the DSL
_current_context = CascadeContext()

def get_current_context() -> CascadeContext:
    return _current_context