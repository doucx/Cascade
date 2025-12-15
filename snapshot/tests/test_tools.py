from unittest.mock import MagicMock
import cascade as cs
from cascade.tools.preview import _analyze_plan
from cascade.tools.events import PlanNodeInspected, PlanAnalysisFinished, PlanAnalysisStarted


def test_dry_run_emits_correct_events_linear():
    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    # Define the workflow
    result = step_b(step_a(), y=10)
    
    # Create a mock bus
    mock_bus = MagicMock()
    
    # Run the core analysis logic
    _analyze_plan(result, mock_bus)

    # Collect all published events
    # mock_bus.publish.call_args_list is a list of calls, each call is (args, kwargs)
    # We want the first arg of each call, which is the event object
    events = [call.args[0] for call in mock_bus.publish.call_args_list]

    # Assert basic sequence
    assert len(events) == 4 # Start + NodeA + NodeB + Finish
    
    assert isinstance(events[0], PlanAnalysisStarted)
    
    # Check Step A
    node_a_event = events[1]
    assert isinstance(node_a_event, PlanNodeInspected)
    assert node_a_event.index == 1
    assert node_a_event.node_name == "step_a"
    assert node_a_event.literal_inputs == {}

    # Check Step B
    node_b_event = events[2]
    assert isinstance(node_b_event, PlanNodeInspected)
    assert node_b_event.index == 2
    assert node_b_event.node_name == "step_b"
    # This assertion replaces the brittle string check "[Literals: {'y': 10}]"
    assert node_b_event.literal_inputs == {'y': 10}

    assert isinstance(events[3], PlanAnalysisFinished)


def test_dry_run_emits_correct_events_diamond():
    @cs.task
    def t_a(): return 1
    @cs.task
    def t_b(x): return x + 1
    @cs.task
    def t_c(x): return x * 2
    @cs.task
    def t_d(y, z): return y + z

    r_d = t_d(t_b(t_a()), z=t_c(t_a()))

    mock_bus = MagicMock()
    _analyze_plan(r_d, mock_bus)
    
    events = [call.args[0] for call in mock_bus.publish.call_args_list]
    
    # Filter only node events
    node_events = [e for e in events if isinstance(e, PlanNodeInspected)]
    assert len(node_events) == 4
    
    names = [e.node_name for e in node_events]
    
    # Assert topological order
    assert names[0] == "t_a"
    assert names[-1] == "t_d"
    assert "t_b" in names[1:3]
    assert "t_c" in names[1:3]