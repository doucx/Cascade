import pytest
from typing import Dict, Callable

from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.triad import RetryNode
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.std.system.retry import standard_retry_logic


@pytest.fixture
def retry_topology_and_runner():
    max_attempts = 3

    # 1. Define Nodes
    d_error_in = PhysicsDataNode(id="D_error_in", name="ErrorInput")
    d_context_in = PhysicsDataNode(id="D_context_in", name="ContextInput")

    f_retry = RetryNode(
        id="F_retry",
        name="RetryLogic",
        max_attempts=max_attempts,
        input_ports={
            "error_in": PortDef("error_in", PortRole.DATA),
            "context_in": PortDef("context_in", PortRole.DATA),
        },
        output_ports={
            "retry_out": PortDef("retry_out", PortRole.DATA),
            "fail_out": PortDef("fail_out", PortRole.DATA),
        },
    )

    d_retry_out = PhysicsDataNode(id="D_retry_out", name="RetryOutput")
    d_fail_out = PhysicsDataNode(id="D_fail_out", name="FailureOutput")

    # 2. Build Graph
    graph = BipartiteGraph()
    for node in [
        d_error_in,
        d_context_in,
        f_retry,
        d_retry_out,
        d_fail_out,
    ]:
        graph.nodes[node.id] = node

    # 3. Define Channels
    graph.channels.extend(
        [
            # Inputs to RetryNode
            Channel(d_error_in.id, "out", f_retry.id, "error_in"),
            Channel(d_context_in.id, "out", f_retry.id, "context_in"),
            # Outputs from RetryNode
            Channel(f_retry.id, "retry_out", d_retry_out.id, "in"),
            Channel(f_retry.id, "fail_out", d_fail_out.id, "in"),
        ]
    )

    # 4. Setup Runner
    function_map: Dict[str, Callable] = {f_retry.id: standard_retry_logic}
    code_registry = CodeRegistry()  # Not needed for stdlib, but runner requires it
    runner = EventDrivenRunner(graph, function_map, code_registry)

    # Yield runner and node IDs for tests to use
    node_ids = {
        "d_error_in": d_error_in.id,
        "d_context_in": d_context_in.id,
        "d_retry_out": d_retry_out.id,
        "d_fail_out": d_fail_out.id,
    }
    yield runner, node_ids


@pytest.mark.asyncio
async def test_retry_path(retry_topology_and_runner):
    runner, nodes = retry_topology_and_runner

    # 1. Prepare tokens. retry_count is 1, which is less than max_attempts (3).
    error_token = Token(payload=ValueError("Transient Error"))
    context_token = Token(payload="original_context", trace={"retry_count": 1})

    # 2. Inject tokens into the memory
    runner.memory.put(runner.graph.nodes[nodes["d_error_in"]], error_token)
    runner.memory.put(runner.graph.nodes[nodes["d_context_in"]], context_token)

    # 3. Drive the reactor for one step
    fired_count = runner.reactor.step()
    assert fired_count == 1

    # 4. Assert correct routing
    assert runner.memory.get_count(nodes["d_retry_out"]) == 1
    assert runner.memory.get_count(nodes["d_fail_out"]) == 0

    # 5. Verify token state
    out_token = runner.memory.take(nodes["d_retry_out"])
    assert out_token.payload == "original_context"
    # standard_retry_logic increments the count *before* checking
    assert out_token.trace["retry_count"] == 2


@pytest.mark.asyncio
async def test_failure_path(retry_topology_and_runner):
    runner, nodes = retry_topology_and_runner

    # 1. Prepare tokens. The logic increments before checking, so a count of 2
    # will become 3, which equals max_attempts (3) and should trigger failure.
    error_token = Token(payload=ValueError("Permanent Error"))
    context_token = Token(payload="original_context", trace={"retry_count": 2})

    # 2. Inject tokens
    runner.memory.put(runner.graph.nodes[nodes["d_error_in"]], error_token)
    runner.memory.put(runner.graph.nodes[nodes["d_context_in"]], context_token)

    # 3. Drive the reactor
    fired_count = runner.reactor.step()
    assert fired_count == 1

    # 4. Assert correct routing
    assert runner.memory.get_count(nodes["d_retry_out"]) == 0
    assert runner.memory.get_count(nodes["d_fail_out"]) == 1

    # 5. Verify token state
    out_token = runner.memory.take(nodes["d_fail_out"])
    # The error token should be the one passed to the failure path
    assert isinstance(out_token.payload, ValueError)
    assert str(out_token.payload) == "Permanent Error"
