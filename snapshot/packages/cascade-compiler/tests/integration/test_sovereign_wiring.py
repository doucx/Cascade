import pytest
from cascade.spec.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.utils.inspector import GraphInspector


@task
def producer():
    return "Hello"


@task
def consumer(msg):
    return f"Received: {msg}"


def test_sovereign_wiring_flow():
    """
    Verifies that the new 'output_default' based wiring actually works
    and connects the producer's Stainer to the consumer's Bleacher.
    """
    # 1. Generate Logical Graph
    t1 = producer()
    t2 = consumer(t1)
    
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate(t2)

    # 2. Build Physical Graph
    builder = Builder()
    physical_graph = builder.build(graph_ir, EnvironmentDef())

    # 3. Inspect Topology
    inspector = GraphInspector(physical_graph)
    
    # Get nodes
    nodes = {n.name: n for n in graph_ir.nodes}
    t1_id = nodes["producer"].id
    t2_id = nodes["consumer"].id

    t1_stainer_id = f"{t1_id}.stain"
    
    # Check that t1.stain has the sovereign port
    inspector.assert_port_exists(t1_stainer_id, "output_default")

    # Find channels from t1.stain
    channels = inspector.find_channels_from(t1_stainer_id, "output_default")
    assert len(channels) == 1
    
    # It should go to a dependency buffer (D_dep)
    d_dep_id = channels[0].target_node_id
    assert "dep." in d_dep_id
    
    # That buffer should go to t2.bleach
    t2_bleacher_id = f"{t2_id}.bleach"
    inspector.assert_connection(d_dep_id, t2_bleacher_id, target_port="msg")