from collections import defaultdict
from typing import Callable, List, Type, Dict, Any
from cascade.spec import EventIR
from .events import Event

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Handler]] = defaultdict(list)
        self._wildcard_subscribers: List[Handler] = []

    def subscribe(self, event_type: Type[Event], handler: Handler):
        if event_type is Event:
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)
        for handler in self._wildcard_subscribers:
            handler(event)

    def publish_ir(self, ir: EventIR):
        event = Event.from_ir(ir)
        self.publish(event)
