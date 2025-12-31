import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskSkipped


@pytest.mark.asyncio
async def test_sequence_executes_in_order(bus_and_spy):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_a():
        execution_order.append("A")

    @cs.task
    def task_b():
        execution_order.append("B")

    @cs.task
    def task_c():
        execution_order.append("C")

    workflow = cs.sequence([task_a(), task_b(), task_c()])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)

    assert execution_order == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_sequence_forwards_last_result(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def first():
        return "first"

    @cs.task
    def last():
        return "last"

    workflow = cs.sequence([first(), last()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == "last"


@pytest.mark.asyncio
async def test_sequence_aborts_on_failure(bus_and_spy):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_ok():
        execution_order.append("ok")

    @cs.task
    def task_fail():
        execution_order.append("fail")
        raise ValueError("This task fails")

    @cs.task
    def task_never():
        execution_order.append("never")

    workflow = cs.sequence([task_ok(), task_fail(), task_never()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="This task fails"):
        await engine.run(workflow)

    assert execution_order == ["ok", "fail"]


@pytest.mark.asyncio
async def test_sequence_aborts_on_skipped_node(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(a):
        return "B"

    @cs.task
    def task_c(b):
        return "C"

    false_condition = cs.task(lambda: False)()
    # task_b will be skipped, which should cause task_c to be skipped too.
    workflow = cs.sequence([task_a(), task_b(1).run_if(false_condition), task_c(2)])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 2

    skipped_names = {event.task_name for event in skipped_events}
    assert skipped_names == {"task_b", "task_c"}

    # Verify task_c was skipped because its sequence dependency was skipped
    task_c_skipped_event = next(e for e in skipped_events if e.task_name == "task_c")
    assert task_c_skipped_event.reason == "UpstreamSkipped_Sequence"


@pytest.mark.asyncio
async def test_pipeline_chains_data_correctly(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    workflow = cs.pipeline(10, [add_one, multiply_by_two])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == 22


@pytest.mark.asyncio
async def test_pipeline_with_lazy_initial_input(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def get_initial():
        return 10

    @cs.task
    def add_one(x):
        return x + 1

    workflow = cs.pipeline(get_initial(), [add_one])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == 11


@pytest.mark.asyncio
async def test_pipeline_with_run_if_data_penetration(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    @cs.task
    def add_three(x):
        return x + 3

    false_condition = cs.task(lambda: False)()
    workflow = cs.pipeline(
        10,
        [
            add_one,
            lambda x: multiply_by_two(x).run_if(false_condition),
            add_three,
        ],
    )

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    # Expected: 10 -> add_one -> 11
    # -> multiply_by_two is skipped
    # -> 11 (from add_one) penetrates to add_three
    # -> 11 + 3 = 14
    assert result == 14

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 1
    assert skipped_events[0].task_name == "multiply_by_two"
