import pytest
import cascade as cs
from cascade.graph import build_graph, StaticGraphError


def test_task_returning_lazy_result_is_forbidden():
    """
    Verifies that the GraphBuilder rejects the anti-pattern of a task
    returning a LazyResult. This violates the static, declarative nature
    of Cascade graphs.
    """

    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        # This is the anti-pattern: a task's logic should not be
        # building new graph components at runtime.
        return task_b()

    workflow = task_a_violating()

    # This test will FAIL initially, because build_graph does not yet
    # raise StaticGraphError. It will pass once the validation is implemented.
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' returns a LazyResult",
    ):
        build_graph(workflow)