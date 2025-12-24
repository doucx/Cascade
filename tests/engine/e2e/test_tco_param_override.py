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


@pytest.mark.asyncio
async def test_jump_overrides_param_complex_path():
    """
    Same as the above test, but forces the ArgumentResolver's "complex path"
    by including a resource injection, ensuring the fix works in both code paths.
    """
    results = []

    # Define a dummy resource to trigger the complex path
    @cs.resource
    def dummy_resource():
        yield "dummy_value"

    @cs.task
    def recursive_task_with_injection(n, injected=cs.inject("dummy_resource")):
        # Ensure resource was injected correctly
        assert injected == "dummy_value"

        if len(results) > 10:
            return "InfiniteLoopDetected"
            
        results.append(n)
        if n <= 0:
            return "Done"
        
        return cs.Jump(target_key="continue", data=n - 1)

    t = recursive_task_with_injection(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    # Register the resource required by the task
    engine.register(dummy_resource)
    
    final_res = await engine.run(t, params={"n": 3})

    assert results == [3, 2, 1, 0]
    assert final_res == "Done"