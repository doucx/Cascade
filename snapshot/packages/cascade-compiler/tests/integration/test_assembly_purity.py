import pickle
import pytest

from cascade.spec.dsl.task import task
from cascade.spec.physical.environment import EnvironmentDef
from cascade.spec.physical.assembly import Assembly
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


def test_assembly_is_serializable_and_pure():
    # 1. Define a representative workflow
    workflow = square(add(1, 2))

    # 2. Compile the workflow into a physical graph
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, environment)
    assembly = artifact.assembly
    assert isinstance(assembly, Assembly)

    # 3. The Purity Test: Attempt to serialize the Assembly
    try:
        serialized_assembly = pickle.dumps(assembly)
        # Optional: check that it can be deserialized correctly
        deserialized_assembly = pickle.loads(serialized_assembly)
    except Exception as e:
        pytest.fail(
            "Assembly purity test failed. The Assembly object is not serializable. "
            f"This likely means a runtime object has been leaked into the "
            f"graph or symbol table. Error: {e}"
        )

    # 4. Verify basic integrity after deserialization
    assert isinstance(deserialized_assembly, Assembly)
    assert len(assembly.graph.nodes) == len(deserialized_assembly.graph.nodes)
    assert assembly.symbol_table.keys() == deserialized_assembly.symbol_table.keys()
