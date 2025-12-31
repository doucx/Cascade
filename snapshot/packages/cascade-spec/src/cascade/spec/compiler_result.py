from dataclasses import dataclass
from typing import Dict, Callable, Any
from cascade.spec.ir.models import GraphIR


@dataclass
class CompilationResult:
    """
    Container for the output of the Compiler Frontend.
    
    Attributes:
        ir: The Intermediate Representation of the compute graph.
        symbol_table: A mapping from structure_hash to the actual callable object.
                      This is used by the runtime to link instructions to code.
    """
    ir: GraphIR
    symbol_table: Dict[str, Callable[..., Any]]