from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class RetryPolicySpec:
    """Serializable specification for retry logic."""
    max_attempts: int = 0
    delay: float = 0.0
    backoff: float = 1.0

@dataclass
class ExecutionPolicy:
    """Aggregate policy for task execution."""
    retry: Optional[RetryPolicySpec] = None
    resources: Dict[str, Any] = field(default_factory=dict)
    timeouts: Dict[str, float] = field(default_factory=dict)  # e.g., {"execution": 60.0}