from typing import Union, Callable, Any, Sequence
from cascade.spec.lazy_types import LazyResult


def sequence(tasks: Sequence[LazyResult]) -> LazyResult:
    if not tasks:
        raise ValueError("cs.sequence requires at least one task.")

    # Chain dependencies: B.after(A), C.after(B), etc.
    for i in range(len(tasks) - 1):
        tasks[i + 1].after(tasks[i])

    return tasks[-1]


def pipeline(
    initial: Any, steps: Sequence[Union[Callable[[Any], Any], LazyResult]]
) -> LazyResult:
    current_result = initial

    for step in steps:
        if isinstance(step, LazyResult):
            # If a LazyResult is passed directly, it's ambiguous how to pass input.
            # We assume it implies a dependency but cannot verify data flow.
            # For a proper pipeline, steps should be Callables (factories).
            # However, to be robust, if it IS a LazyResult, we just sequence it?
            # No, 'pipeline' implies data flow.
            raise TypeError(
                f"Pipeline steps must be callables (Task factories), got {type(step)}. "
                "Did you call the task (e.g. 'my_task()') instead of passing the function 'my_task'?"
            )
        elif callable(step):
            # Apply the factory to the current result
            current_result = step(current_result)
        else:
            raise TypeError(f"Invalid pipeline step type: {type(step)}")

    # Ensure the result is a LazyResult (if initial was a literal and no steps were run)
    # But pipeline usually implies at least one step or initial is Lazy.
    # If initial is literal and steps empty, it returns literal.
    # The caller expects a LazyResult usually, but returning literal is valid for Cascade (it will just resolve).
    # But to be safe in DSL usage, let's allow it.

    return current_result
