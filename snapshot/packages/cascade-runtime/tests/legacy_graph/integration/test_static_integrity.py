import cascade.sdk as cs
import pytest
from cascade.execution.graph.model.exceptions import StaticGraphError


@pytest.mark.asyncio
async def test_task_returning_lazy_result_is_forbidden_at_runtime(engine):
    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        return task_b()

    workflow = task_a_violating()

    # Use default engine fixture
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' illegally returned a LazyResult",
    ):
        await engine.run(workflow)
