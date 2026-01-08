from typing import Any, Tuple, Dict, Callable, Optional
from cascade.compiler.frontend.generator import IRGenerator
from cascade.runtime.graph.adapter import IRToRuntimeAdapter
from cascade.runtime.graph.model import Graph, Node
from cascade.runtime.graph.registry import NodeRegistry


def build_graph(
    target: Any, registry: Optional[NodeRegistry] = None
) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
    """
    Legacy compatibility layer for graph building.
    Internally uses the Cascade Compiler (IRGenerator) and Runtime Adapter.
    """
    # 1. Generate Intermediate Representation (IR)
    ir = IRGenerator().generate(target)

    # 2. Adapt IR to Runtime Object Model
    # We pass the registry to ensure node interning/deduplication works as expected
    adapter = IRToRuntimeAdapter(registry=registry)
    return adapter.adapt(ir)