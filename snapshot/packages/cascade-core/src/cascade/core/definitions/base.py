from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from cascade.core.identity.fingerprint import Fingerprint


@dataclass
class Definition:
    """
    Base class for all IR Level 0 definitions.
    
    A Definition represents a raw declaration from the user DSL (e.g. a Task, a SQL query).
    It is the input to the Compiler, which will lower it into an executable Op.
    """
    
    # The unique identity of this definition, calculated based on its content.
    # Populated by the Compiler during the identification phase.
    fingerprint: Optional[Fingerprint] = None

    # User-defined metadata that does not affect the execution identity
    # (e.g., UI labels, descriptions).
    metadata: Dict[str, Any] = field(default_factory=dict)