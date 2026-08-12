from __future__ import annotations

from typing import Any, Callable

from cascade.compiler.frontend.generator import IRGenerator
from cascade.execution.graph.model.adapter import IRToRuntimeAdapter
from cascade.execution.graph.model.model import Graph, Node
from cascade.execution.graph.model.registry import NodeRegistry


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> tuple[Graph, dict[str, Node], dict[str, Callable]]:
    # 1. Generate Intermediate Representation (IR)
    ir = IRGenerator().generate(target)

    # 2. Adapt IR to Runtime Object Model
    # We pass the registry to ensure node interning/deduplication works as expected
    adapter = IRToRuntimeAdapter(registry=registry)
    return adapter.adapt(ir)
