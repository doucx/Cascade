import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@cs.task
def generate_range(n: int) -> list[int]:
    return list(range(n))


@cs.task
def double(x: int) -> int:
    return x * 2


@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)


@pytest.mark.asyncio
async def test_map_reduce_pipeline():
    # 1. Generate dynamic input: [0, 1, 2, 3, 4]
    nums = generate_range(5)

    # 2. Map: [0, 2, 4, 6, 8]
    doubled_nums = double.map(x=nums)

    # 3. Reduce: 20
    # Here doubled_nums is a MappedLazyResult.
    # The engine must resolve this to [0, 2, 4, 6, 8] before calling sum_all.
    total = sum_all(numbers=doubled_nums)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(total)

    assert result == 20
