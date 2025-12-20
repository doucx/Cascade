from rich.panel import Panel
from rich.text import Text
from rich.console import Console, ConsoleOptions, RenderResult
from typing import Dict, Any

class StatusBar:
    """
    A Rich-renderable object for displaying key-value status information.
    """
    def __init__(self, initial_status: Dict[str, Any] = None):
        self.status_data = initial_status or {}

    def set_status(self, key: str, value: Any):
        """Update a status value."""
        self.status_data[key] = value

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """The Rich render protocol method."""
        status_text = Text(no_wrap=True)
        for i, (key, value) in enumerate(self.status_data.items()):
            if i > 0:
                status_text.append(" | ", style="dim")
            status_text.append(f"{key}: ", style="cyan")
            status_text.append(str(value), style="bold magenta")
            
        yield Panel(status_text, title="[bold]Experiment Status[/bold]", border_style="dim")