import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    Event,
    TaskExecutionFinished,
    RunFinished,
)


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def event_names(self):
        return [type(e).__name__ for e in self.events]


def test_e2e_linear_workflow():
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = asyncio.run(engine.run(final_greeting))

    assert result == "Hello, {name}!".format(name="Cascade")

    assert spy.event_names() == [
        "RunStarted",
        "TaskExecutionStarted",
        "TaskExecutionFinished",
        "TaskExecutionStarted",
        "TaskExecutionFinished",
        "RunFinished",
    ]

    # Assert specific event details
    assert spy.events[1].task_name == "get_name"
    assert spy.events[2].status == "Succeeded"
    assert spy.events[2].result_preview == "'Cascade'"
    assert spy.events[4].status == "Succeeded"
    assert spy.events[5].status == "Succeeded"


def test_e2e_diamond_workflow_and_result():
    @cs.task
    def t_a():
        return 5

    @cs.task
    def t_b(x):
        return x * 2  # 10

    @cs.task
    def t_c(x):
        return x + 3  # 8

    @cs.task
    def t_d(y, z):
        return y + z  # 18

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = asyncio.run(engine.run(r_d))
    assert result == 18


def test_e2e_failure_propagation():
    @cs.task
    def ok_task():
        return True

    @cs.task
    def failing_task(x):
        raise ValueError("Something went wrong")

    @cs.task
    def unreachable_task(y):
        return False

    r1 = ok_task()
    r2 = failing_task(r1)
    r3 = unreachable_task(r2)

    import asyncio

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        asyncio.run(engine.run(r3))

    assert spy.event_names() == [
        "RunStarted",
        "TaskExecutionStarted",  # ok_task started
        "TaskExecutionFinished",  # ok_task finished
        "TaskExecutionStarted",  # failing_task started
        "TaskExecutionFinished",  # failing_task finished
        "RunFinished",
    ]

    # Assert success of the first task
    task_ok_finished = spy.events[2]
    assert isinstance(task_ok_finished, TaskExecutionFinished)
    assert task_ok_finished.task_name == "ok_task"
    assert task_ok_finished.status == "Succeeded"

    # Assert failure of the second task
    task_fail_finished = spy.events[4]
    assert isinstance(task_fail_finished, TaskExecutionFinished)
    assert task_fail_finished.task_name == "failing_task"
    assert task_fail_finished.status == "Failed"
    assert "ValueError: Something went wrong" in task_fail_finished.error

    # Assert failure of the entire run
    run_finished = spy.events[5]
    assert isinstance(run_finished, RunFinished)
    assert run_finished.status == "Failed"
