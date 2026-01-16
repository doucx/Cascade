# This test is heavily dependent on the VM's execution logic.
# Since the compiler's role is to produce a valid graph, we can simplify this test
# to focus on the static topology generation for resources, rather than simulating the VM.
# The full backpressure simulation is better suited for cascade-vm tests.

import pytest

from cascade.spec.dsl.task import task
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.compiler.utils.inspector import GraphInspector


@task(constraints={"gpu": 1})
def use_gpu():
    return "using gpu"


def test_resource_wiring_topology_is_correct():
    # 1. Define workflow
    workflow = use_gpu()

    # 2. Compile
    generator = IRGenerator()
    builder = Builder()
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, env)
    physical_graph = artifact.assembly.graph

    # 3. Inspect
    inspector = GraphInspector(physical_graph)
    task_id = workflow._uuid
    physical_id = artifact.manifest.logical_to_physical_map[task_id]

    launcher_id = f"{physical_id}.launch"
    lander_id = f"{physical_id}.land"
    req_id = f"req.{physical_id}.gpu"
    gnt_id = f"gnt.to.{physical_id}.gpu"
    allocator_id = "canonical.resource.allocator.gpu"
    reclaimer_id = "canonical.resource.reclaimer.gpu"
    req_buffer_id = "buffer.req.gpu"
    rel_buffer_id = "buffer.rel.gpu"

    # Assert Request Chain: F_req -> D_buffer -> F_allocator
    inspector.assert_connection(req_id, req_buffer_id)
    inspector.assert_connection(req_buffer_id, allocator_id)

    # Assert Grant Chain: F_allocator -> D_gnt -> F_launcher
    inspector.assert_connection(allocator_id, gnt_id, source_port=f"gnt_for_{req_id}")
    inspector.assert_connection(gnt_id, launcher_id, target_port="res_gpu")

    # Assert Release Chain: F_lander -> D_buffer -> F_reclaimer
    inspector.assert_connection(lander_id, rel_buffer_id, source_port="res_gpu")
    inspector.assert_connection(rel_buffer_id, reclaimer_id)