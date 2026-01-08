from enum import StrEnum


class NodePrefix(StrEnum):
    """
    Standard prefixes for Physical Node IDs.
    These define the 'Atomic Type' of the node in the physical topology.
    """

    # Data Nodes (Places)
    CONST = "const"  # Constant value holder
    PULSE = "pulse"  # Event trigger (0 tokens, infinite capacity)
    LEDGER = "ledger"  # Resource state holder
    BUFFER = "buffer"  # Queue for resources or data
    PARKED = "parked"  # Parking lot for pending requests
    SIGNAL = "signal"  # Signaling channel
    EGRESS = "egress"  # Exit point
    INGRESS = "ingress"  # Entry point (reserved)

    # Function Nodes (Transitions)
    BLEACH = "bleach"  # Triad: Pre-process
    WORKER = "worker"  # Triad: Execution
    STAIN = "stain"    # Triad: Post-process
    REQ = "req"        # Resource Requestor
    GATE = "gate"      # Control Gate
    PROBE = "probe"    # Introspection Probe

    # Global/System
    GLOBAL = "global"  # Global singleton
    CANONICAL = "canonical"  # Canonical resource broker