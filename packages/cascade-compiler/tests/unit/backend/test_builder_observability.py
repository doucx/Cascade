import pytest
from cascade.spec.ir.models import GraphIR
from cascade.spec.environment import EnvironmentDef
from cascade.spec.triad import ObservabilityNode
from cascade.compiler.backend.builder import Builder


@pytest.fixture
def empty_graph_ir():
    # Even with no user tasks, the observability infrastructure should be present
    # (D_life and F_obs are global singletons)
    return GraphIR(nodes=[])


def test_builder_creates_observer_sidecar(empty_graph_ir):
    builder = Builder()
    graph = builder.build(empty_graph_ir, environment=EnvironmentDef())

    # 1. Assert D_life exists (Baseline check)
    assert "global.observability.bus" in graph.nodes

    # 2. Assert F_obs exists (New Requirement)
    f_obs_id = "global.observability.observer"
    assert f_obs_id in graph.nodes
    f_obs = graph.nodes[f_obs_id]
    assert isinstance(f_obs, ObservabilityNode)

    # 3. Assert Connection: D_life -> F_obs
    obs_channels = [
        c
        for c in graph.channels
        if c.source_node_id == "global.observability.bus"
        and c.target_node_id == f_obs_id
    ]
    assert len(obs_channels) == 1
    channel = obs_channels[0]

    # 4. Assert Port Mapping
    # D_life is a DataNode, source_port is typically "out"
    assert channel.source_port == "out"
    # F_obs expects input on "event_token" port (per standard_observer signature)
    assert channel.target_port == "event_token"
