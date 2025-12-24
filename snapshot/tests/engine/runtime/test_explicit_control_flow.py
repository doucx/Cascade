import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.mark.asyncio
async def test_explicit_jump_loop():
    """
    Tests the core explicit state transition mechanism.
    - A task returns a `cs.Jump` signal.
    - `cs.bind` statically connects the task to a `cs.select_jump` chooser.
    - The engine interprets the jump and reschedules the next task with new data,
      bypassing graph rebuilding.
    """

    @cs.task
    def counter(n: int):
        if n <= 0:
            # On terminal condition, signal to exit the loop
            return cs.Jump(target_key="exit", data=n)
        else:
            # Signal to continue the loop, passing n-1 as the new input
            return cs.Jump(target_key="continue", data=n - 1)

    # Define the starting point of the loop
    loop_node = counter(5)

    # Define the jump selector, which maps keys from Jump signals to tasks
    jump_selector = cs.select_jump(
        {
            "continue": loop_node,  # "continue" jumps back to the start of the loop
            "exit": None,  # "exit" breaks the loop
        }
    )

    # Statically bind the control flow: the result of `loop_node` is routed
    # to the `jump_selector`. This creates a structural `ITERATIVE_JUMP` edge.
    cs.bind(loop_node, jump_selector)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # The target is the loop_node itself. The engine should follow the jump
    # signals until the "exit" key is returned.
    final_result = await engine.run(loop_node)

    # The loop should terminate when n is 0, and the data from the final
    # jump signal (n=0) should be the return value.
    assert final_result == 0