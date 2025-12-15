from dataclasses import dataclass, field
from typing import Any, Dict, List
from ..runtime.events import Event


@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    """Fired when dry_run starts analyzing a target."""
    target_node_id: str = ""
    
    def _get_payload(self) -> Dict[str, Any]:
        return {"target_node_id": self.target_node_id}


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "literal_inputs": self.literal_inputs
        }


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    """Fired when dry_run analysis is complete."""
    total_steps: int = 0

    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}