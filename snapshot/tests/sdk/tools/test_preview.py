import cascade as cs
from cascade.runtime.bus import MessageBus
from cascade.tools.preview import _analyze_plan, DryRunConsoleSubscriber
from cascade.tools.events import (
    PlanNodeInspected,
    PlanAnalysisFinished,
    PlanAnalysisStarted,
)


def test_dry_run_emits_correct_events_linear(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a(), y=10)
    _analyze_plan(result, bus)

    # Assert basic sequence
    assert len(spy.events) == 4  # Start + NodeA + NodeB + Finish
    assert isinstance(spy.events_of_type(PlanAnalysisStarted)[0], PlanAnalysisStarted)
    assert isinstance(spy.events_of_type(PlanAnalysisFinished)[0], PlanAnalysisFinished)

    node_events = spy.events_of_type(PlanNodeInspected)
    assert len(node_events) == 2

    # Check Step A
    node_a_event = node_events[0]
    assert node_a_event.index == 1
    assert node_a_event.node_name == "step_a"
    assert node_a_event.input_bindings == {}

    # Check Step B
    node_b_event = node_events[1]
    assert node_b_event.index == 2
    assert node_b_event.node_name == "step_b"
    assert "y" in node_b_event.input_bindings


def test_dry_run_emits_correct_events_diamond(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_d = t_d(t_b(r_a), z=t_c(r_a))

    _analyze_plan(r_d, bus)

    node_events = spy.events_of_type(PlanNodeInspected)
    assert len(node_events) == 4

    names = [e.node_name for e in node_events]

    # Assert topological order
    assert names[0] == "t_a"
    assert names[-1] == "t_d"
    assert "t_b" in names[1:3]
    assert "t_c" in names[1:3]


def test_console_subscriber_renders_correctly(capsys):
    """
    Tests the View layer independently for correct formatting.
    """
    bus = MessageBus()
    DryRunConsoleSubscriber(bus)

    # 1. Publish Start Event
    bus.publish(PlanAnalysisStarted(target_node_id="root"))
    captured = capsys.readouterr()
    assert "---" in captured.out
    assert "Execution Plan" in captured.out

    # 2. Publish Node Event
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            literal_inputs={"param": 42},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "'param': 42" in captured.out

    # 3. Publish Finish Event
    bus.publish(PlanAnalysisFinished(total_steps=2))
    captured = capsys.readouterr()
    assert "---" in captured.out
