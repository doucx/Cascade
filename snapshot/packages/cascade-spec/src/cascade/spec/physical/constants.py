from enum import StrEnum


class NodePrefix(StrEnum):
    # Data Nodes (Places)
    CONST = "const"  # Constant value holder
    PULSE = "pulse"  # Event trigger (0 tokens, infinite capacity)
    LEDGER = "ledger"  # Resource state holder
    BUFFER = "buffer"  # Queue for resources or data
    PARKED = "parked"  # Parking lot for pending requests
    SIGNAL = "signal"  # Signaling channel
    EGRESS = "egress"  # Exit point
    INGRESS = "ingress"  # Entry point (reserved)
    RESULT = "result"  # Async result holder (DataNode)

    # Function Nodes (Transitions)
    LAUNCH = "launch"  # Dyad: Launcher (Prepare & Dispatch)
    LAND = "land"  # Dyad: Lander (Receive & Finalize)
    BLEACH = "bleach"  # Triad: Pre-process (Deprecated)
    WORKER = "worker"  # Triad: Execution (Deprecated)
    STAIN = "stain"  # Triad: Post-process (Deprecated)
    REQ = "req"  # Resource Requestor
    GATE = "gate"  # Control Gate
    PROBE = "probe"  # Introspection Probe
    SLEEP = "sleep"  # Time delay requestor

    # Data Node Subtypes
    WAKEUP = "wakeup"  # Return point for a sleep operation

    # Global/System
    GLOBAL = "global"  # Global singleton
    CANONICAL = "canonical"  # Canonical resource broker
