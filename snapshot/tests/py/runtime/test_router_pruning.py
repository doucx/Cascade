import pytest
import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event, TaskSkipped
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.events.append)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]

@pytest.mark.asyncio
async def test_pruning_exclusive_branches():
    """
    Test that branches exclusive to a router are pruned when not selected.
    """
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def branch_a():
        return "A"

    @cs.task
    def branch_b(val):
        return "B" # Should be pruned

    @cs.task
    def dummy_dep():
        return "DEP"

    @cs.task
    def branch_b_upstream(dep):
        return "B_UP" # Should also be pruned (recursive)

    # branch_b depends on branch_b_upstream
    # branch_b_upstream depends on dummy_dep
    # This pushes branch_b_upstream to Stage 1, while get_route (selector) is in Stage 0.
    # This ensures pruning happens BEFORE branch_b_upstream is scheduled.
    b_chain = branch_b(branch_b_upstream(dummy_dep()))

    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(), "b": b_chain}
    )

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(workflow)
    assert result == "A"

    # Check pruning events
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}
    
    assert "branch_b" in skipped_names
    assert "branch_b_upstream" in skipped_names
    
    # Verify reasons
    for e in skipped:
        assert e.reason == "Pruned"


@pytest.mark.asyncio
async def test_pruning_shared_dependency():
    """
    Test that a dependency shared between branches (or external tasks) 
    is NOT pruned even if one consumer branch is pruned.
    """
    @cs.task
    def get_route():
        return "a"

    @cs.task
    def shared_task():
        return "SHARED"

    @cs.task
    def branch_a(dep):
        return f"A({dep})"

    @cs.task
    def branch_b(dep):
        return f"B({dep})" # Should be pruned, but 'dep' should not

    # shared_task is used by BOTH branches
    shared = shared_task()
    
    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(shared), "b": branch_b(shared)}
    )

    @cs.task
    def consumer(val):
        return val

    workflow = consumer(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    result = await engine.run(workflow)
    assert result == "A(SHARED)"

    # Check pruning
    skipped = spy.events_of_type(TaskSkipped)
    skipped_names = {e.task_name for e in skipped}

    assert "branch_b" in skipped_names
    assert "shared_task" not in skipped_names # MUST NOT be pruned

    # Only branch_b should be pruned
    assert len(skipped) == 1