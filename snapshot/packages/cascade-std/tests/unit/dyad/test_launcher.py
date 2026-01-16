import time
from unittest.mock import MagicMock, patch

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
    # Setup Inputs
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_launcher_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute
    standard_launcher(inputs, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]
    
    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_refs == {"arg1": "hello", "arg2": 123}
    assert "start_ts" in request.trace


def test_standard_launcher_emits_observability_event():
    node = create_mock_launcher_node({})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Use IO capture (simulated by return value in test harness, 
    # but strictly standard_launcher uses @implements which returns dict)
    # The @implements decorator logic wraps it, but for unit testing the inner function logic:
    # We need to simulate the IO wrapper if we were testing the inner logic directly,
    # OR we invoke the decorated function. standard_launcher IS the decorated function.
    
    outputs = standard_launcher({}, node, resources)

    assert "obs_output" in outputs
    obs_token = outputs["obs_output"]
    assert obs_token.payload["t"] == "task.lifecycle"
    assert obs_token.payload["data"]["state"] == "Running"