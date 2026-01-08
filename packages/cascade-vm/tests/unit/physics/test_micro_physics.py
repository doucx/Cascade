import pytest

from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.triad import StainNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal


# --- Mocks ---


def mock_worker_success(inputs, node, resources):
    return {"worker_result": Token(payload="Success")}


def mock_worker_failure(inputs, node, resources):
    return {"worker_result": Token(payload=ValueError("Boom!"))}


# --- Tests ---


@pytest.mark.asyncio
async def test_physics_the_spark():
    d_in = PhysicsDataNode(
        id="D_in", name="Input", initial_tokens=1, initial_payload="Spark"
    )
    f_node = PhysicsFuncNode(
        id="F_proc",
        name="Processor",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
    d_out = PhysicsDataNode(id="D_out", name="Output")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_node, d_out]}

    # Wiring
    graph.channels.append(Channel(d_in.id, "out", f_node.id, "in"))
    graph.channels.append(Channel(f_node.id, "out", d_out.id, "in"))

    # Logic: Simple identity
    def identity(inputs, node, res):
        return {"out": inputs["in"]}

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_node.id: identity}, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # Action
    fired = reactor.step()

    # Verification
    assert fired == 1
    assert memory.get_count(d_in.id) == 0  # Consumed
    assert memory.get_count(d_out.id) == 1  # Produced
    assert memory.take(d_out.id).payload == "Spark"


@pytest.mark.asyncio
async def test_physics_the_crash():
    # Topology: D_in -> Stainer -> (D_ok, D_err)
    # We simulate the stainer receiving a failed result from a worker

    d_res = PhysicsDataNode(id="D_res", name="WorkerResult")  # Holds the Exception
    d_trace = PhysicsDataNode(id="D_trace", name="TraceCtx")

    f_stain = StainNode(
        id="F_stain",
        name="Stainer",
        input_ports={
            "worker_result": PortDef("worker_result", PortRole.DATA),
            "trace_input": PortDef("trace_input", PortRole.DATA),
        },
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "output_error": PortDef("output_error", PortRole.DATA),  # Sovereign Port
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    d_ok = PhysicsDataNode(id="D_ok", name="SuccessPath")
    d_err = PhysicsDataNode(id="D_err", name="ErrorPath")
    d_obs = PhysicsDataNode(id="global.observability.bus", name="Bus", capacity=100)

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_res, d_trace, f_stain, d_ok, d_err, d_obs]}

    # Wiring
    graph.channels.append(Channel(d_res.id, "out", f_stain.id, "worker_result"))
    graph.channels.append(Channel(d_trace.id, "out", f_stain.id, "trace_input"))

    graph.channels.append(Channel(f_stain.id, "output_default", d_ok.id, "in"))
    graph.channels.append(Channel(f_stain.id, "output_error", d_err.id, "in"))
    graph.channels.append(Channel(f_stain.id, "obs_output", d_obs.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_stain.id: standard_stainer}, resources)
    reactor = Reactor(graph, memory, kernel)

    # Inject Fault
    memory.put(d_res, Token(payload=ValueError("Micro-Physics Failure")))
    memory.put(d_trace, Token(payload={"rid": "test-crash"}))

    # Action
    fired = reactor.step()

    # Verification
    assert fired == 1

    # 1. Error Path should be active
    assert memory.get_count(d_err.id) == 1
    err_token = memory.take(d_err.id)
    assert isinstance(err_token.payload, ValueError)

    # 2. Success Path should be empty (Sovereign Routing)
    assert memory.get_count(d_ok.id) == 0


@pytest.mark.asyncio
async def test_physics_the_halt():
    d_trig = PhysicsDataNode(id="D_trig", name="Trigger", initial_tokens=1)
    f_halt = PhysicsFuncNode(
        id="F_halt",
        name="Terminator",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )

    # Note: F_halt output is usually not wired to a DataNode in user graphs,
    # but for physics validity, it emits a token. Reactor intercepts it.
    # We wire it to a dummy node just to satisfy graph validity if needed,
    # though Reactor intercepts ControlTokens before putting them in memory.
    d_void = PhysicsDataNode(id="D_void", name="Void")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_trig, f_halt, d_void]}

    graph.channels.append(Channel(d_trig.id, "out", f_halt.id, "in"))
    graph.channels.append(Channel(f_halt.id, "out", d_void.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_halt.id: halt_signal}, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # Pre-condition
    assert not reactor.shutdown_event.is_set()

    # Action
    fired = reactor.step()

    # Verification
    assert fired == 1

    # The Reactor should have intercepted the HALT signal
    assert reactor.shutdown_event.is_set()

    # The D_void node should represent the fact that the token was 'intercepted' or processed?
    # Actually, Reactor._handle_results_immediate does:
    # 1. Check Control Signal
    # 2. Handle Sinks
    # 3. Handle Outbound Channels
    # Current implementation does NOT stop propagation if control signal is found.
    # So D_void might still get the token.
    # Let's check implementation details:
    # It calls _handle_control_signal but continues to loop over channels.
    # So the SystemControlToken physically travels to D_void too.
    assert memory.get_count(d_void.id) == 1
    token = memory.take(d_void.id)
    assert isinstance(token.payload, SystemControlToken)
    assert token.payload.command == ControlCommand.HALT
