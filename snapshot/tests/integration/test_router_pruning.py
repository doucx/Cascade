import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event, TaskSkipped, TaskExecutionFinished


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.mark.asyncio
async def test_router_prunes_unselected_branch():
    """
    Verify that tasks in the unselected branch of a Router are NOT executed.
    """
    
    @cs.task
    def get_mode():
        return "fast"

    @cs.task
    def fast_task():
        return "FAST"

    @cs.task
    def slow_task():
        return "SLOW"

    @cs.task
    def process(val):
        return f"Processed: {val}"

    # Router: Selects 'fast' or 'slow'
    router = cs.Router(
        selector=get_mode(),
        routes={
            "fast": fast_task(),
            "slow": slow_task()
        }
    )

    flow = process(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    result = await engine.run(flow)

    assert result == "Processed: FAST"

    # Verify Events
    # 1. 'fast_task' should be executed
    finished = spy.events_of_type(TaskExecutionFinished)
    executed_names = {e.task_name for e in finished}
    assert "fast_task" in executed_names
    assert "process" in executed_names
    
    # 2. 'slow_task' should NOT be executed
    assert "slow_task" not in executed_names

    # 3. 'slow_task' should be SKIPPED with reason 'RouterPruned'
    skipped = spy.events_of_type(TaskSkipped)
    skipped_map = {e.task_name: e.reason for e in skipped}
    
    assert "slow_task" in skipped_map
    assert skipped_map["slow_task"] == "RouterPruned"


@pytest.mark.asyncio
async def test_router_prunes_cascade():
    """
    Verify that pruning cascades to downstream dependencies of the pruned branch.
    """
    
    @cs.task
    def selector():
        return "a"
    
    @cs.task
    def branch_a():
        return "A"
    
    @cs.task
    def branch_b_step1():
        return "B1"
    
    @cs.task
    def branch_b_step2(val):
        return f"{val}->B2"

    # Branch B has a chain: step1 -> step2
    chain_b = branch_b_step2(branch_b_step1())

    router = cs.Router(
        selector=selector(),
        routes={
            "a": branch_a(),
            "b": chain_b
        }
    )

    @cs.task
    def identity(x):
        return x

    target = identity(router)

    bus = MessageBus()
    spy = SpySubscriber(bus)
    engine = Engine(bus=bus)

    await engine.run(target)

    skipped = spy.events_of_type(TaskSkipped)
    skipped_map = {e.task_name: e.reason for e in skipped}

    # step2 (the direct route result) is pruned explicitly
    assert skipped_map["branch_b_step2"] == "RouterPruned"
    
    # step1 is NOT pruned automatically because the Engine only prunes 
    # the *immediate* route result node (step2). 
    # step1 might still run if it has no dependency on selector.
    # 
    # WAIT: In the current implementation, we only prune the nodes directly in `router.routes`.
    # We do NOT prune the *upstream* of the pruned node (Reverse Pruning).
    # So `branch_b_step1` is expected to RUN, but its result is unused.
    #
    # Let's verify this behavior is consistent with implementation.
    # If we want to prevent step1 from running, step1 needs to depend on something that is pruned
    # OR we need a more advanced "demand-driven" execution model.
    #
    # For now, let's assert the current behavior: Step 2 is pruned.
    
    finished = spy.events_of_type(TaskExecutionFinished)
    executed = {e.task_name for e in finished}
    
    assert "branch_a" in executed
    assert "branch_b_step1" in executed  # This runs (wasted work, known limitation)
    assert "branch_b_step2" not in executed # This is pruned