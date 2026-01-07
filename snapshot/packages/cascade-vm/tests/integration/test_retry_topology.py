import pytest
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.triad import RetryNode
from cascade.spec.physical.nodes import PhysicsDataNode, Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.assembly import Assembly, SymbolTable
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry


@pytest.fixture
def retry_harness():
    """Builds a BipartiteGraph and an EventDrivenRunner for testing retry logic."""
    # 1. Define Nodes
    d_error = PhysicsDataNode(id="d.error", name="ErrorIn")
    d_context = PhysicsDataNode(id="d.context", name="ContextIn")
    d_retry_loop = PhysicsDataNode(id="d.retry_loop", name="RetryOut")
    d_permanent_fail = PhysicsDataNode(id="d.permanent_fail", name="FailOut")

    # The node under test
    f_retry = RetryNode(
        id="f.retry",
        name="RetryLogic",
        max_attempts=2,  # We will test against this policy
        input_ports={
            "error_in": PortDef("error_in", PortRole.DATA),
            "context_in": PortDef("context_in", PortRole.DATA),
        },
        output_ports={
            "retry_out": PortDef("retry_out", PortRole.DATA),
            "fail_out": PortDef("fail_out", PortRole.DATA),
        },
    )

    # 2. Define Channels
    channels = [
        # Inputs to RetryNode
        Channel("d.error", "out", "f.retry", "error_in"),
        Channel("d.context", "out", "f.retry", "context_in"),
        # Outputs from RetryNode
        Channel("f.retry", "retry_out", "d.retry_loop", "in"),
        Channel("f.retry", "fail_out", "d.permanent_fail", "in"),
    ]

    # 3. Assemble Graph and Harness
    graph = BipartiteGraph(
        nodes={
            n.id: n
            for n in [
                d_error,
                d_context,
                f_retry,
                d_retry_loop,
                d_permanent_fail,
            ]
        },
        channels=channels,
    )

    assembly = Assembly(graph=graph, symbol_table=dict())
    # The runner's linker will automatically map the RetryNode type to its implementation
    runner = EventDrivenRunner.from_assembly(assembly, CodeRegistry())
    runner.prime()

    return runner, {
        "error": "d.error",
        "context": "d.context",
        "retry": "d.retry_loop",
        "fail": "d.permanent_fail",
    }


def test_retry_logic_succeeds_on_first_attempt(retry_harness):
    runner, ids = retry_harness

    # Input: No prior retries (retry_count=0)
    error_token = Token(payload=RuntimeError("First failure"))
    context_token = Token(payload={"input": 1}, trace={"retry_count": 0})

    # Inject tokens to trigger the retry node
    runner.memory.put(runner.graph.nodes[ids["error"]], error_token)
    runner.memory.put(runner.graph.nodes[ids["context"]], context_token)

    # Execute one step of the reactor
    fired_count = runner.reactor.step()
    assert fired_count == 1

    # Assert: The context token should be routed to the retry loop
    assert runner.memory.get_count(ids["retry"]) == 1
    assert runner.memory.get_count(ids["fail"]) == 0

    # Verify the retry_count was incremented in the trace
    out_token = runner.memory.take(ids["retry"])
    assert out_token.trace.get("retry_count") == 1


def test_retry_logic_fails_on_exhaustion(retry_harness):
    runner, ids = retry_harness

    # Input: This is the last attempt (retry_count=1, max_attempts=2)
    error_token = Token(payload=RuntimeError("Second failure"))
    context_token = Token(payload={"input": 1}, trace={"retry_count": 1})

    # Inject tokens
    runner.memory.put(runner.graph.nodes[ids["error"]], error_token)
    runner.memory.put(runner.graph.nodes[ids["context"]], context_token)

    # Execute
    fired_count = runner.reactor.step()
    assert fired_count == 1

    # Assert: The error token should be routed to the permanent failure node
    assert runner.memory.get_count(ids["retry"]) == 0
    assert runner.memory.get_count(ids["fail"]) == 1

    # Verify the correct token was passed through
    out_token = runner.memory.take(ids["fail"])
    assert out_token is error_token
