import pytest
import asyncio
from cascade.runtime.host.instance import Engine
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.services.observability.bus import EventBus
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
def engine(executor, bus, strategy):
    # Solver is not used by VMStrategy but required by Engine interface
    solver = MockSolver(plan=[])
    
    return Engine(
        solver=solver,
        executor=executor,
        bus=bus,
        strategy=strategy,
        object_store=InMemoryObjectStore()
    )


# --- Tests ---

@pytest.mark.asyncio
async def test_vm_simple_execution(engine):
    """Test executing a single synchronous task."""
    workflow = add(1, 2)
    result = await engine.run(workflow)
    assert result == 3


@pytest.mark.asyncio
async def test_vm_async_execution(engine):
    """Test executing a single asynchronous task."""
    workflow = async_mul(3, 4)
    result = await engine.run(workflow)
    assert result == 12


@pytest.mark.asyncio
async def test_vm_dependency_chain(engine):
    """Test a chain of dependencies: (1 + 2) * 3."""
    sum_res = add(1, 2)
    workflow = async_mul(sum_res, 3)
    
    result = await engine.run(workflow)
    assert result == 9


@pytest.mark.asyncio
async def test_vm_error_propagation(engine):
    """Test that exceptions are propagated correctly."""
    workflow = fail("Boom!")
    
    with pytest.raises(ValueError, match="Boom!"):
        await engine.run(workflow)


@pytest.mark.asyncio
async def test_vm_list_output(engine):
    """Test that the VM can return a list of results (implicit gather)."""
    t1 = add(1, 1)
    t2 = add(2, 2)
    workflow = [t1, t2]
    
    result = await engine.run(workflow)
    assert result == [2, 4]