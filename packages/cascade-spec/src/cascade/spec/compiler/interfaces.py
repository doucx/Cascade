from typing import Any, Protocol

from ..ir.graph import NodeIR
from .model import SubGraph


class ExpansionPolicy(Protocol):
    def expand(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...


class WiringPolicy(Protocol):
    def setup_globals(self, ctx: Any) -> None: ...
    def apply(self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph) -> None: ...


class ResourcePrism(Protocol):
    def ensure_globals(self, ctx: Any, res_def: Any) -> None: ...
    def expand_task(
        self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any
    ) -> None: ...
    def wire_task(
        self, ctx: Any, node_ir: NodeIR, subgraph: SubGraph, res_name: str, amount: Any
    ) -> None: ...
