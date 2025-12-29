import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node
from cascade.spec.task import task


from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint


def test_local_executor_sync_execution():
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = Node(structural_id="add", definition=stub_def, callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_add, resolved_args, resolved_kwargs))

    assert result == 17  # 5 + 10 + 2


def test_local_executor_async_execution():
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    # Must explicit set is_async=True for the executor to treat it as a coroutine
    stub_def = TaskDef(
        name="async_add", args=[], fingerprint=Fingerprint(), is_async=True
    )
    node_async = Node(
        structural_id="async_add", definition=stub_def, callable_obj=async_add.func
    )

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_async, resolved_args, resolved_kwargs))

    assert result == 6
