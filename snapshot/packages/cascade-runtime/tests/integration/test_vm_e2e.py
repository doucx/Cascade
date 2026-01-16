import pytest
import asyncio
from cascade.runtime.host.instance import Engine
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.bus.core import EventBus
from cascade.runtime.storage import InMemoryObjectStore
from cascade.spec.dsl.task import task
from cascade.test_utils.helpers import MockSolver


# --- Tasks ---


@task
def add(a: int, b: int) -> int:
    return a + b


@task
async def async_mul(a: int, b: int) -> int:
    await asyncio.sleep(0.01)
    return a * b


@task
def fail(msg: str):
    raise ValueError(msg)


# --- Fixtures ---


@pytest.fixture
def executor():
    return LocalExecutor()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def strategy(executor, bus):
    return VMExecutionStrategy(executor=executor, bus=bus)


@pytest.fixture
def engine(engine_factory, executor, bus, strategy):
    # Solver is not used by VMStrategy but required by Engine interface
    solver = MockSolver(plan=[])

    return engine_factory(
        solver=solver,
        executor=executor,
        bus=bus,
        strategy=strategy,
        object_store=InMemoryObjectStore(),
    )


# --- Tests ---


@pytest.mark.asyncio
async def test_vm_simple_execution(engine):
    workflow = add(1, 2)
    result = await engine.run(workflow)
    assert result == 3


@pytest.mark.asyncio
async def test_vm_async_execution(engine):
    workflow = async_mul(3, 4)
    result = await engine.run(workflow)
    assert result == 12


@pytest.mark.asyncio
async def test_vm_dependency_chain(engine):
    sum_res = add(1, 2)
    workflow = async_mul(sum_res, 3)

    result = await engine.run(workflow)
    assert result == 9


@pytest.mark.asyncio
async def test_vm_error_propagation(engine):
    workflow = fail("Boom!")

    with pytest.raises(ValueError, match="Boom!"):
        await engine.run(workflow)


@pytest.mark.asyncio
async def test_vm_list_output(engine):
    t1 = add(1, 1)
    t2 = add(2, 2)
    workflow = [t1, t2]

    result = await engine.run(workflow)
    assert result == [2, 4]
