import sys
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

@pytest.mark.asyncio
async def test_mutual_recursion_tco_optimization(engine):
    """
    Verifies that mutual recursion (A -> B -> A) is optimized via TCO.
    If the engine builds a new graph for every step without releasing memory/stack,
    or if it fails to use the fast path, this might be slow or crash on low-resource envs.
    
    But primarily we check correctness here. The O(1) property is verified by 
    inspecting internal cache behavior if we wanted to be deeper.
    """
    
    # Increase depth to ensure we exceed default stack limits if TCO fails
    # Standard Python recursion limit is 1000. We do 2000 steps (1000 loops).
    sys.setrecursionlimit(1500)
    TOTAL_STEPS = 2000

    @cs.task
    def task_a(n: int):
        if n <= 0:
            return "Done"
        return task_b(n - 1)

    @cs.task
    def task_b(n: int):
        if n <= 0:
            return "Done"
        return task_a(n - 1)

    # Force analysis to ensure cycle IDs are assigned (though engine should do it)
    # from cascade.graph.ast_analyzer import assign_tco_cycle_ids
    # assign_tco_cycle_ids(task_a)
    
    result = await engine.run(task_a(TOTAL_STEPS))
    assert result == "Done"

    # Verify that cycle IDs were assigned
    assert getattr(task_a, "_tco_cycle_id", None) is not None
    assert getattr(task_b, "_tco_cycle_id", None) is not None
    assert getattr(task_a, "_tco_cycle_id") == getattr(task_b, "_tco_cycle_id")