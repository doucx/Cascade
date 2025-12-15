import asyncio
from cascade.spec.task import task

def test_task_detects_sync_function():
    @task
    def sync_fn():
        return 1
    
    assert sync_fn.is_async is False

def test_task_detects_async_function():
    @task
    async def async_fn():
        return 1
    
    assert async_fn.is_async is True

def test_async_task_returns_lazy_result():
    @task
    async def async_fn(x):
        return x + 1
    
    # Even for async tasks, calling them should return a LazyResult immediately,
    # not a coroutine object.
    result = async_fn(10)
    assert result.task.name == "async_fn"
    assert result.args == (10,)