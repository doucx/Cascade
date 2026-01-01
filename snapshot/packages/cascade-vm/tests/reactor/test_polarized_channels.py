import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.spec.topology import ChannelKind
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished, Channel

@pytest.mark.asyncio
async def test_dual_barrier_activation_waits_for_all_inputs():
    """
    Verifies that a FuncNode only fires after BOTH its data and signal
    inputs are excited. This is the core test for the dual-barrier logic.
    """
    # 1. Setup Topology
    f_node = FuncNode(name="process")
    d_data = DataNode(name="data_in")
    d_signal = DataNode(name="signal_in")

    # Wire inputs with different kinds
    f_node.add_input(Port(name="data_arg", source=d_data, kind=ChannelKind.DATA))
    f_node.add_input(Port(name="signal_arg", source=d_signal, kind=ChannelKind.SIGNAL))

    # 2. Setup Reactor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    reactor.register_node(f_node)
    reactor.register_node(d_data)
    reactor.register_node(d_signal)

    # 3. Step 1: Inject DATA only
    reactor.push_event(TokenGenerated(node=d_data, token=Token("some_data")))
    await reactor.step()

    # Assertion 1: Executor should NOT be called yet
    mock_executor.submit.assert_not_called()
    assert f_node.is_ready() is False, "Node should not be ready with only data input"

    # 4. Step 2: Inject SIGNAL
    reactor.push_event(TokenGenerated(node=d_signal, token=Token(None))) # Signal token has no payload
    await reactor.step()
    
    # Assertion 2: Executor SHOULD be called now. This is the ultimate proof
    # that is_ready() returned True inside the reactor.step() call.
    mock_executor.submit.assert_called_once()

    call_args = mock_executor.submit.call_args[0]
    submitted_node = call_args[0]
    submitted_inputs = call_args[1]

    assert submitted_node == f_node
    # Assert that DATA token was passed correctly
    assert submitted_inputs["data_arg"].payload == "some_data"
    # Assert that SIGNAL token was consumed but NOT passed to executor
    assert "signal_arg" not in submitted_inputs


@pytest.mark.asyncio
async def test_signal_channel_strips_payload():
    """
    Verifies that the Reactor's routing logic creates a new, payload-less
    token when routing through a SIGNAL channel.
    """
    # 1. Setup Topology
    f_source = FuncNode(name="source")
    d_target_data = DataNode(name="data_dest")
    d_target_signal = DataNode(name="signal_dest")
    
    # 2. Setup Channels with different kinds from the same source
    data_channel = Channel(
        source=f_source,
        target=d_target_data,
        output_name="result",
        kind=ChannelKind.DATA
    )
    signal_channel = Channel(
        source=f_source,
        target=d_target_signal,
        output_name="result",
        kind=ChannelKind.SIGNAL
    )

    # 3. Setup Reactor
    reactor = Reactor(executor=AsyncMock())
    reactor.register_channel(data_channel)
    reactor.register_channel(signal_channel)

    # 4. Simulate an ExecutionFinished event with a payload
    original_token = Token(payload="SECRET_DATA", tag="default", metadata={"id": 1})
    event = ExecutionFinished(node=f_source, outputs={"result": original_token})
    reactor.push_event(event)

    # 5. Process the event
    await reactor.step()

    # 6. Assertions
    # Data channel should have the original token
    token_in_data = d_target_data.peek()
    assert token_in_data is not None
    assert token_in_data.payload == "SECRET_DATA"
    assert token_in_data.metadata == {"id": 1}

    # Signal channel should have a new token with payload=None
    token_in_signal = d_target_signal.peek()
    assert token_in_signal is not None
    assert token_in_signal.payload is None
    assert token_in_signal.metadata == {"id": 1} # Metadata should be preserved