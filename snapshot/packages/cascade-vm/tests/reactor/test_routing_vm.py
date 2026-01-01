import pytest
from unittest.mock import AsyncMock
from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, ExecutionFinished, Channel


@pytest.mark.asyncio
async def test_routing_tag_matching():
    """
    Case 1: Tag Matching & Routing
    验证 Reactor 根据 Token 的 tag 正确选择 Channel。

    拓扑: F -> (Tag='default') -> D_next
         F -> (Tag='continue') -> D_loop
    """
    # 1. Topology
    f_node = FuncNode(name="decision")
    d_next = DataNode(name="next")
    d_loop = DataNode(name="loop")

    # 2. Define Channels (The edges of the Bipartite Graph)
    # Channel connects a specific output port of a FuncNode to a DataNode, with a filter.
    c_default = Channel(
        source=f_node, target=d_next, output_name="result", tag_filter="default"
    )

    c_loop = Channel(
        source=f_node, target=d_loop, output_name="result", tag_filter="continue"
    )

    # 3. Setup Reactor
    reactor = Reactor(executor=AsyncMock())
    # We assume Reactor manages topology (channels)
    reactor.register_channel(c_default)
    reactor.register_channel(c_loop)

    # 4. Simulate F producing a 'continue' token
    token = Token(payload=1, tag="continue")

    # The Executor would emit this event
    event = ExecutionFinished(node=f_node, outputs={"result": token})
    reactor.push_event(event)

    # 5. Step
    await reactor.step()

    # 6. Assertions
    # D_loop should receive the token because tags match
    assert d_loop.is_excited()
    assert d_loop.peek() == token

    # D_next should remain empty because 'continue' != 'default'
    assert d_next.is_empty()


@pytest.mark.asyncio
async def test_routing_fan_out_same_tag():
    """
    Case 2: Broadcasting
    验证同一个 Tag 可以被多个 Channel 接收 (Fan-out)。
    """
    f_node = FuncNode(name="broadcast")
    d_1 = DataNode(name="d1")
    d_2 = DataNode(name="d2")

    # Both channels accept 'default'
    c1 = Channel(source=f_node, target=d_1, output_name="out", tag_filter="default")
    c2 = Channel(source=f_node, target=d_2, output_name="out", tag_filter="default")

    reactor = Reactor(executor=AsyncMock())
    reactor.register_channel(c1)
    reactor.register_channel(c2)

    token = Token(payload="msg", tag="default")
    event = ExecutionFinished(node=f_node, outputs={"out": token})
    reactor.push_event(event)

    await reactor.step()

    # Both should receive the token (Copy semantics for broadcast)
    assert d_1.peek().payload == "msg"
    assert d_2.peek().payload == "msg"
