from dataclasses import dataclass, field
from typing import Dict, Any

from .topology import BipartiteGraph

# The SymbolTable defines the mapping between a physical node's ID
# in the graph and the canonical hash of its executable code structure.
SymbolTable = Dict[str, str]


@dataclass(frozen=True)
class Assembly:
    # The physical topology, defining nodes (What) and channels (How).
    graph: BipartiteGraph

    # The symbol table, mapping physical node IDs to canonical code structure hashes.
    # Key: Physical Node ID (e.g., "hash123.worker")
    # Value: Canonical Code Structure Hash (e.g., "sha256:abc...")
    symbol_table: SymbolTable = field(default_factory=dict)

    # Metadata about the assembly, such as compiler version, build time, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)
