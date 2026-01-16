import pytest
import cascade.sdk as cs


@pytest.mark.asyncio
async def test_explicit_jump_loop(engine):
    @cs.task
    def counter(n: int):
        if n <= 0:
            return cs.Jump(target_key="exit", data=n)
        else:
            return cs.Jump(target_key="continue", data=n - 1)

    loop_node = counter(5)

    jump_selector = cs.select_jump(
        {
            "continue": loop_node,
            "exit": None,
        }
    )

    cs.bind(loop_node, jump_selector)

    # Use the default engine fixture
    final_result = await engine.run(loop_node)

    assert final_result == 0
