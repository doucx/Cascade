# Standard library of physical primitives (ICs) for the Cascade VM.

from .dyad.lander import standard_lander
from .dyad.launcher import standard_launcher
from .resource.continuous import continuous_allocator, continuous_reclaimer
from .resource.discrete import discrete_allocator, discrete_reclaimer

# Resource
from .resource.requestor import resource_requestor
from .system.drainer import drain_signal
from .system.egress import standard_egress

# System
from .system.gate import gate_passthrough

# Legacy Triad (Keep for backward compatibility until full migration)
from .system.observer import standard_observer
from .system.retry import standard_retry_logic
from .system.terminator import halt_signal
from .system.time import standard_sleep

__all__ = [
    "continuous_allocator",
    "continuous_reclaimer",
    "discrete_allocator",
    "discrete_reclaimer",
    "drain_signal",
    "gate_passthrough",
    "halt_signal",
    "resource_requestor",
    "standard_egress",
    "standard_lander",
    "standard_launcher",
    "standard_observer",
    "standard_retry_logic",
    "standard_sleep",
]
