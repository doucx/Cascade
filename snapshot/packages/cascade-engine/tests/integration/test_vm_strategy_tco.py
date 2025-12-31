import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.spec.jump import Jump


@pytest.mark.asyncio
async def test_vm_strategy_handles_explicit_jump_loop():
    """
    Integration Test: VM Strategy TCO Support
    
    Verifies that VMExecutionStrategy correctly interprets cs.Jump signals returned 
    by tasks, implementing a "Trampoline" or Loop at the strategy level.
    
    Scenario:
    - A 'counter' task decrements a value.
    - If val > 0: Returns Jump("continue", val-1)
    - If val <= 0: Returns "done"
    """
    
    # 1. Define the Task
    @cs.task
    def counter(val: int):
        if val > 0:
            return cs.Jump("continue", val - 1)
        return "done"

    # 2. Define the Workflow
    # Initial state: val = 3
    # Logic: 3 -> Jump(2) -> 2 -> Jump(1) -> 1 -> Jump(0) -> "done"
    start_node = counter(3)
    
    # 3. Define Routing Logic
    # We map the "continue" key back to the counter task itself (recursion)
    # Note: In standard Cascade, we bind the selector to the node.
    jump_selector = cs.select_jump({
        "continue": start_node, 
    })
    cs.bind(start_node, jump_selector)

    # 4. Setup Engine
    # We use Real Components to ensure full integration
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 5. Execute with VM Strategy
    # This assumes the engine supports the 'use_vm=True' flag from previous refactors
    result = await engine.run(start_node, use_vm=True)

    # 6. Assertions
    # If TCO is working, we get the final string.
    # If TCO is missing (Current State), we likely get the first Jump object returned by counter(3).
    assert result == "done", f"Expected 'done', got {result}"

@pytest.mark.asyncio
async def test_vm_strategy_handles_jump_with_data_passing():
    """
    Integration Test: Data Passing in Jumps
    
    Verifies that data payload in Jump(target, data) is correctly applied 
    as input overrides for the next iteration.
    """
    @cs.task
    def accumulator(acc: int, limit: int):
        if acc < limit:
            # Pass updated 'acc' to next iteration, keep 'limit'
            return cs.Jump("next", {"acc": acc + 1})
        return acc

    node = accumulator(acc=0, limit=3)
    
    selector = cs.select_jump({
        "next": node
    })
    cs.bind(node, selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # Should loop: 0 -> 1 -> 2 -> 3 (stop)
    result = await engine.run(node, use_vm=True)
    
    assert result == 3
