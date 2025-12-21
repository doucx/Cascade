import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_dict_provider():
    @cs.task
    def get_val():
        return "dynamic_value"

    workflow = cs.dict(
        static_key="static",
        dynamic_key=get_val()
    )

    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == {
        "static_key": "static",
        "dynamic_key": "dynamic_value"
    }


@pytest.mark.asyncio
async def test_format_provider():
    @cs.task
    def get_name():
        return "World"

    workflow = cs.format("Hello, {name}!", name=get_name())

    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_format_provider_with_positional_args():
    @cs.task
    def get_first():
        return "first"

    @cs.task
    def get_second():
        return "second"

    workflow = cs.format("Positional: {}, {}", get_first(), get_second())
    
    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == "Positional: first, second"