from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from .events import Event

# Define a Handler type alias for clarity
Handler = Callable[[Any], None]

class MessageBus:
    """
    A simple in-memory message bus for dispatching events to subscribers.
    """
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Handler]] = defaultdict(list)
        self._wildcard_subscribers: List[Handler] = []

    def subscribe(self, event_type: Type[Event], handler: Handler):
        """Register a handler for a specific event type."""
        if event_type is Event:
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        """Dispatch an event to all relevant subscribers."""
        # 1. Dispatch to handlers explicitly subscribed to this event type
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        
        # 2. Dispatch to wildcard handlers (subscribed to Event)
        for handler in self._wildcard_subscribers:
            handler(event)