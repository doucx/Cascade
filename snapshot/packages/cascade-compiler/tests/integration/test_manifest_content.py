
from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


@task
def source():
    return "start"


def test_manifest_is_populated_correctly():
    # 1. Define a workflow with clear entry and exit points
    # Entry: source(), const 1, const 2
    # Exit: square()
    workflow = square(add(source(), 2))

    # We need the logical ID of the root to verify the exit point
    root_logical_id = workflow._uuid

    # 2. Compile
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
    manifest = artifact.manifest

    # 3. Assert Entry Points
    # We expect one pulse node (for source) and one const node (for value 2).
    # The first argument to add() is from source(), not a const.
    assert len(manifest.entry_points) == 2

    # Check that entries look correct
    assert any(ep.startswith("pulse.source.") for ep in manifest.entry_points)
    assert any(ep.startswith("const.") for ep in manifest.entry_points)

    # 4. Assert Exit Points
    assert len(manifest.exit_points) == 1
    assert root_logical_id in manifest.exit_points

    exit_node_id = manifest.exit_points[root_logical_id]
    assert exit_node_id.startswith("egress.")
    assert exit_node_id.endswith(root_logical_id)
