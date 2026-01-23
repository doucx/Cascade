from unittest.mock import MagicMock

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.dyad import LauncherNode
from cascade.std.dyad.launcher import standard_launcher
from cascade.spec.runtime import ComputeRequest


def create_mock_launcher_node(input_ports_config):
    node = MagicMock(spec=LauncherNode)
    node.id = "test_node.launch"
    node.name = "Launch(test_node)"
    node.reply_to_nid = "test_node.result"
    node.canonical_code_structure_hash = "abc-123"
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node


def test_standard_launcher_dispatches_request():
    # Use IO capture wrapper to simulate reactor behavior
    from cascade.spec.physics.binding import IOWrapper
    from cascade.spec.specs.dyad import LauncherSpec

    # Setup Inputs for the IO Wrapper
    io_inputs = {
        "0": Token(payload="hello"),  # Positional
        "kwarg": Token(payload=123),  # Keyword
    }
    node = create_mock_launcher_node(
        {"0": PortRole.DATA, "kwarg": PortRole.DATA, "obs_output": PortRole.OBSERVABILITY}
    )
    io = IOWrapper(io_inputs, {}, LauncherSpec)

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute the raw function logic
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    raw_launcher(io, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]

    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_args == ["hello"]
    assert request.input_kwargs == {"kwarg": 123}
    assert "start_ts" in request.trace


def test_standard_launcher_emits_observability_event():
    node = create_mock_launcher_node({})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    from cascade.spec.physics.binding import implements
    from cascade.std.dyad.launcher import standard_launcher as raw_launcher

    # The decorated function is what we should test
    decorated_launcher = implements(LauncherSpec)(raw_launcher)

    outputs = decorated_launcher({}, node, resources)

    assert "obs_output" in outputs
    obs_token = outputs["obs_output"]
    assert obs_token.payload["t"] == "task.lifecycle"
    assert obs_token.payload["data"]["state"] == "Running"
