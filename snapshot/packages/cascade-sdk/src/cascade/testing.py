from contextlib import contextmanager
from typing import Callable, Any
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


@contextmanager
def override_resource(
    engine: "Engine", name: str, new_resource_func: Callable[[], Any]
):
    """
    A context manager to temporarily override a resource for testing purposes.

    Usage:
        engine = Engine()
        engine.register(production_db)

        with override_resource(engine, "production_db", mock_db):
            engine.run(my_task) # my_task will receive mock_db
    """
    if not hasattr(engine, "override_resource_provider"):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]
