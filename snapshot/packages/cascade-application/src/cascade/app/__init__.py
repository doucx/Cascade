from typing import Any, Dict, List, Tuple, Union

# Use a string forward reference to avoid circular dependency at this stage
if "LazyResult" not in globals():
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from cascade.spec.lazy_types import LazyResult


class CascadeApp:
    """
    The central manager for a workflow's lifecycle, encapsulating all
    infrastructure, configuration, and top-level operations.
    """

    def __init__(self, target: Union["LazyResult", List[Any], Tuple[Any, ...]]):
        """
        Initializes the application context for a given workflow target.

        This constructor is responsible for:
        - Setting up the internal Engine, MessageBus, and other infrastructure.
        - Applying pre-processing to the target, such as auto-gathering lists.
        """
        pass

    def run(self, params: Dict[str, Any] = None) -> Any:
        """Executes the workflow and returns the final result."""
        pass

    def visualize(self) -> str:
        """Generates and returns a Graphviz DOT string of the workflow."""
        pass

    def dry_run(self) -> None:
        """Builds and prints the execution plan without running any tasks."""
        pass