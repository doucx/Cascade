from dataclasses import dataclass, field
from typing import Dict, Any

from cascade.spec.physical.topology import BipartiteGraph

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


@dataclass(frozen=True)
class CompilationManifest:
    # Maps logical UUIDs (from LazyResult) to the base physical node ID.
    # Key: Logical UUID
    # Value: Physical Base ID (current_node_instance_hash)
    logical_to_physical_map: Dict[str, str] = field(default_factory=dict)

    # List of physical DataNode IDs that are initial sources of energy (e.g., const, pulse)
    entry_points: List[str] = field(default_factory=list)

    # Maps the logical UUID of a root LazyResult to the physical DataNode ID
    # that will hold its final result.
    exit_points: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompilationArtifact:
    assembly: Assembly
    manifest: CompilationManifest
