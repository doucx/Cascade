from enum import Enum
from dataclasses import dataclass


class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"


@dataclass
class PortDef:
    name: str
    role: PortRole
    type_hint: str = "Any"


class PortName:
    # Resources
    REQ = "req_in"
    REL = "rel_in"
    GNT = "gnt_out"
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"

    # Worker
    WORKER_INPUT = "worker_input"
    WORKER_RESULT = "worker_result"

    # Trace
    TRACE_INPUT = "trace_input"
    TRACE_OUTPUT = "trace_output"

    # Observability
    OBS_OUTPUT = "obs_output"
    EVENT_TOKEN = "event_token"
