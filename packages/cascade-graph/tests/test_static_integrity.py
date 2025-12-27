import pytest
import cascade as cs
from cascade.graph import StaticGraphError
from cascade.runtime import Engine, MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_task_returning_lazy_result_is_forbidden_at_runtime():
    @cs.task
    def task_b():
        return "B"

    @cs.task
    def task_a_violating():
        # This is the anti-pattern: a task's logic should not be
        # building new graph components at runtime. It should return data or a Jump.
        return task_b()

    workflow = task_a_violating()

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # This test will FAIL initially because the LocalExecutor does not yet
    # raise StaticGraphError. It will pass once the validation is implemented.
    with pytest.raises(
        StaticGraphError,
        match="Task 'task_a_violating' illegally returned a LazyResult",
    ):
        await engine.run(workflow)
