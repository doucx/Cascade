from contextlib import contextmanager

from cascade.runtime import Engine


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
