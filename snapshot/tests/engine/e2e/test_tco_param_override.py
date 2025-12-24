import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.bus import MessageBus

@pytest.mark.asyncio
async def test_jump_overrides_param():
    """
    Test that data provided by cs.Jump (input_overrides) takes precedence over
    upstream dependencies (like cs.Param) defined in the static graph.
    """
    results = []

    @cs.task
    def recursive_task(n):
        # Safety break to prevent infinite loop if bug exists
        if len(results) > 10:
            return "InfiniteLoopDetected"
            
        results.append(n)
        if n <= 0:
            return "Done"
        
        # Pass n-1 to the next iteration
        return cs.Jump(target_key="continue", data=n - 1)

    # Define workflow: Initial input comes from a Param (Edge dependency)
    # If the bug exists, the Jump data (n-1) will be ignored, and Param (3) will be used every time.
    t = recursive_task(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    
    # Run with initial param n=3
    final_res = await engine.run(t, params={"n": 3})

    # Expect: [3, 2, 1, 0]
    # If bug: [3, 3, 3, ...] -> "InfiniteLoopDetected"
    assert results == [3, 2, 1, 0]
    assert final_res == "Done"