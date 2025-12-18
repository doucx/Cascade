import sys
from typing import TextIO, Optional

from rich.console import Console
from rich.theme import Theme

from cascade.common.messaging import protocols, MessageStore

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

# Define a custom theme for Rich
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "data": "green",
})


class RichCliRenderer(protocols.Renderer):
    """
    A renderer that uses the 'rich' library for formatted, colorful output.
    """

    def __init__(
        self,
        store: MessageStore,
        min_level: str = "INFO",
    ):
        self._store = store
        self._console = Console(theme=custom_theme, stderr=True)
        self._data_console = Console() # For stdout
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            message = self._store.get(msg_id, **kwargs)
            
            # Use style tags that match our theme
            style = level.lower() if level.lower() in custom_theme.styles else ""
            
            self._console.print(message, style=style)