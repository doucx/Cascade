# Standard library of physical primitives (ICs) for the Cascade VM.

from .dyad.launcher import standard_launcher
from .dyad.lander import standard_lander

# Legacy Triad (Keep for backward compatibility until full migration)
from .triad.dispatcher import standard_dispatcher
from .triad.bleacher import standard_bleacher
from .triad.stainer import standard_stainer
from .triad.observer import standard_observer

# System
from .system.gate import gate_passthrough
from .system.retry import standard_retry_logic
from .system.time import standard_sleep
from .system.egress import standard_egress
from .system.drainer import drain_signal
from .system.terminator import halt_signal

# Resource
from .resource.requestor import resource_requestor
from .resource.discrete import discrete_allocator, discrete_reclaimer
from .resource.continuous import continuous_allocator, continuous_reclaimer

__all__ = [
    "standard_launcher",
    "standard_lander",
    "standard_dispatcher",
    "standard_bleacher",
    "standard_stainer",
    "standard_observer",
    "gate_passthrough",
    "standard_retry_logic",
    "standard_sleep",
    "standard_egress",
    "drain_signal",
    "halt_signal",
    "resource_requestor",
    "discrete_allocator",
    "discrete_reclaimer",
    "continuous_allocator",
    "continuous_reclaimer",
]