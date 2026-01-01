import pytest
from unittest.mock import AsyncMock

# These imports will fail initially, which is expected for TDD RED state
from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished


@pytest.mark.asyncio
async def test_reactor_event_driven_potential_update():
    """
    Case 1 (Event Driven):
    验证 Reactor 能够处理 TokenGenerated 事件并更新下游节点的势能。
    """
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1", canonical_code_structure_hash="hash_f1")
    # NOTE: We DO NOT wire d_node to f_node.
    # This test is ONLY to verify that the TokenGenerated event correctly
    # updates the state of the DataNode itself, without triggering a fire.

    # 2. Setup Reactor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)

    # Register nodes so Reactor tracks them
    reactor.register_node(d_node)
    reactor.register_node(f_node)

    # 3. Action: Simulate a token generation event
    token = Token(payload=42)
    event = TokenGenerated(node=d_node, token=token)

    # Push event (Reactor buffers it)
    reactor.push_event(event)

    # 4. Process one step of the reactor loop
    await reactor.step()

    # 5. Assertions
    # The data node should now hold the token
    assert d_node.peek() == token
    # The function node should be ready because its input is excited
    assert f_node.is_ready()
    # At this stage, we haven't triggered firing logic, just potential update verification
    # (Or if step() includes firing, verify executor calls in next test)


@pytest.mark.asyncio
async def test_reactor_execution_dispatch():
    """
    Case 2 (Execution Dispatch):
    构造 D_in -> F -> D_out 网络。
    验证当 D_in 激发时，Reactor 自动将 F 提交给 Executor。
    """
    # 1. Topology
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", canonical_code_structure_hash="hash_process")

    f_node.add_input(Port(name="arg", source=d_in))
    f_node.add_output(Port(name="res", target=d_out))

    # 2. Reactor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    reactor.register_node(d_in)
    reactor.register_node(d_out)
    reactor.register_node(f_node)

    # 3. Inject Initial State via Event
    initial_token = Token(10)
    reactor.push_event(TokenGenerated(node=d_in, token=initial_token))

    # 4. Run Loop
    # Step should:
    # a. Process TokenGenerated -> Update D_in -> Update F potential
    # b. Detect F is ready -> Fire F -> Submit to Executor
    await reactor.step()

    # 5. Assertions
    assert mock_executor.submit.called

    call_args = mock_executor.submit.call_args
    # submit(node, inputs)
    submitted_node = call_args[0][0]
    submitted_inputs = call_args[0][1]

    assert submitted_node == f_node
    assert submitted_inputs["arg"].payload == 10

    # Verify atomicity: tokens should be consumed from input
    assert d_in.is_empty()


@pytest.mark.asyncio
async def test_reactor_propagation():
    """
    Case 3 (Propagation):
    验证 Executor 完成任务后，Reactor 能处理结果并将新 Token 放入下游节点。
    """
    # 1. Topology
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", canonical_code_structure_hash="hash_process")
    f_node.add_output(Port(name="res", target=d_out))

    reactor = Reactor(executor=AsyncMock())
    reactor.register_node(f_node)
    reactor.register_node(d_out)

    # 2. Simulate Executor finishing a task (callback or event)
    output_tokens = {"res": Token(20)}
    event = ExecutionFinished(node=f_node, outputs=output_tokens)

    reactor.push_event(event)

    # 3. Process
    await reactor.step()

    # 4. Assertions
    assert d_out.is_excited()
    assert d_out.peek().payload == 20
