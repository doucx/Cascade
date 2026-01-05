from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    # Base path for cascade-spec source
    base = Path("packages/cascade-spec/src/cascade/spec").absolute()

    # ==========================================
    # 1. DSL Layer (Domain Specific Language)
    # ==========================================
    # Fluent Interface & Types
    spec.add(Move(base / "lazy_types.py", base / "dsl/fluent.py"))
    
    # Core DSL Entities
    spec.add(Move(base / "task.py",       base / "dsl/task.py"))
    # resource.py -> dsl/resources.py (Renamed to plural to match 'inputs')
    spec.add(Move(base / "resource.py",   base / "dsl/resources.py"))
    # input.py -> dsl/inputs.py (Renamed to plural)
    spec.add(Move(base / "input.py",      base / "dsl/inputs.py"))
    
    # Control Flow & Routing
    spec.add(Move(base / "jump.py",       base / "dsl/jump.py"))
    spec.add(Move(base / "routing.py",    base / "dsl/routing.py"))
    spec.add(Move(base / "constraint.py", base / "dsl/constraint.py"))

    # ==========================================
    # 2. IR Layer (Intermediate Representation)
    # ==========================================
    # Graph Models
    # Note: Using Move for single file inside existing ir dir
    spec.add(Move(base / "ir/models.py",  base / "ir/graph.py"))
    # Fingerprinting
    spec.add(Move(base / "fingerprint.py", base / "ir/fingerprint.py"))

    # ==========================================
    # 3. Physical Layer (Physics & Topology)
    # ==========================================
    # Core Physics Nodes
    spec.add(Move(base / "physics.py",     base / "physical/nodes.py"))
    # Topology & Channels
    spec.add(Move(base / "topology.py",    base / "physical/topology.py"))
    # Special Nodes (Bleach, Stain, Worker)
    spec.add(Move(base / "triad.py",       base / "physical/triad.py"))
    # Ports & Roles
    spec.add(Move(base / "ports.py",       base / "physical/ports.py"))
    # Environment Definitions
    spec.add(Move(base / "environment.py", base / "physical/environment.py"))
    # Resource Slots (Physical)
    spec.add(Move(base / "resources.py",   base / "physical/resources.py"))
    # Assembly & Symbol Table
    spec.add(Move(base / "assembly.py",    base / "physical/assembly.py"))
    # Bindings
    spec.add(Move(base / "binding.py",     base / "physical/binding.py"))

    # ==========================================
    # 4. Runtime Layer (Interfaces & Telemetry)
    # ==========================================
    # Protocols & Interfaces
    spec.add(Move(base / "protocols.py",     base / "runtime/interfaces.py"))
    # Observability (Events IR)
    spec.add(Move(base / "observability.py", base / "runtime/observability.py"))
    # Telemetry (Headers & Events)
    spec.add(Move(base / "telemetry.py",     base / "runtime/telemetry.py"))
    # System Control
    spec.add(Move(base / "system.py",        base / "runtime/system.py"))