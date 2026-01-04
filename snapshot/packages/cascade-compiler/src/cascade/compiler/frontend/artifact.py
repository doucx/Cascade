from dataclasses import dataclass, field
from typing import Dict, Callable
from cascade.spec.ir.models import GraphIR


@dataclass
class CompilationArtifact:
    """
    The holistic output of the compilation process.
    It contains not just the structural IR, but also the semantic links
    required to execute and debug the graph.
    """

    # The structural blueprint of the computation
    graph_ir: GraphIR

    # The Linker Table: Canonical Node Hash -> Python Executable (Function)
    # Used by the VM to initialize the instruction pointer for each node.
    registry: Dict[str, Callable] = field(default_factory=dict)

    # The Source Map: LazyResult UUID -> Canonical Node Hash
    # Used by the Runtime to bridge user-facing objects (LazyResult) to physical nodes.
    source_map: Dict[str, str] = field(default_factory=dict)