from cascade.spec.dsl.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.compiler.utils.inspector import GraphInspector


@task
def producer():
    return "Hello"


@task
def consumer(msg):
    return f"Received: {msg}"


def test_sovereign_wiring_flow():
    # 1. Generate Logical Graph
    t1 = producer()
    t2 = consumer(t1)

    ir_generator = IRGenerator()
    generation_result = ir_generator.generate(t2)
    graph_ir = generation_result.ir

    # 2. Build Physical Graph
    builder = Builder()
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly
    physical_graph = assembly.graph

    # 3. Inspect Topology
    inspector = GraphInspector(physical_graph)

    # Get nodes
    nodes = {n.name: n for n in graph_ir.nodes}
    t1_id = nodes["producer"].current_node_instance_hash
    t2_id = nodes["consumer"].current_node_instance_hash

    t1_land_id = f"{t1_id}.land"

    # Check that t1.land has the sovereign port
    inspector.assert_port_exists(t1_land_id, "output_default")

    # Find channels from t1.land
    channels = inspector.find_channels_from(t1_land_id, "output_default")
    assert len(channels) == 1

    # It should go to a dependency buffer (D_dep)
    d_dep_id = channels[0].target_node_id
    assert "dep." in d_dep_id

    # That buffer should go to t2.launch
    t2_launch_id = f"{t2_id}.launch"
    inspector.assert_connection(d_dep_id, t2_launch_id, target_port="msg")
