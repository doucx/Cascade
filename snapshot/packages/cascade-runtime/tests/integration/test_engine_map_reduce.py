import pytest
import cascade.sdk as cs


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
async def test_map_reduce_pipeline(engine):
    # 1. Generate dynamic input: [0, 1, 2, 3, 4]
    nums = generate_range(5)

    # 2. Map: [0, 2, 4, 6, 8]
    doubled_nums = double.map(x=nums)

    # 3. Reduce: 20
    total = sum_all(numbers=doubled_nums)

    result = await engine.run(total)

    assert result == 20