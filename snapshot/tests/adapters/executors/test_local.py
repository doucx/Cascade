import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node
from cascade.spec.task import task


def test_local_executor_sync_execution():
    """
    Tests that the LocalExecutor can execute a synchronous function
    with resolved positional and keyword arguments.
    """

    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node (Only callable_obj is needed here)
    node_add = Node(id="add", name="add", callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_add, resolved_args, resolved_kwargs))

    assert result == 17  # 5 + 10 + 2


def test_local_executor_async_execution():
    """
    Tests that the LocalExecutor can execute an asynchronous function.
    """

    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    node_async = Node(id="async_add", name="async_add", callable_obj=async_add.func)

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_async, resolved_args, resolved_kwargs))

    assert result == 6
