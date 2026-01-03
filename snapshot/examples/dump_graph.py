import sys
from pathlib import Path

# This is a common pattern for running scripts in a monorepo project root.
# It ensures that the 'src' directories of our packages are on the Python path.
# NOTE: This assumes you run the script from the project's root directory.
# An alternative is to do an editable install of the workspace (`uv pip install -e .`).
workspace_root = Path(__file__).parent.parent
sys.path.append(str(workspace_root / "packages/cascade-spec/src"))
sys.path.append(str(workspace_root / "packages/cascade-compiler/src"))
sys.path.append(str(workspace_root / "packages/cascade-std/src"))


from cascade.spec.task import task
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.compiler.utils import GraphDumper


# --- 1. Define a simple workflow ---
@task
def task_a(x: int):
    """A simple source task."""
    return x * 2


@task
def task_b(a_val: int, y: int):
    """A task that depends on another."""
    return a_val + y


def main():
    """
    Builds a simple physical graph and dumps its DOT representation to stdout.
    """
    print("--- Cascade Physical Graph Dumper ---", file=sys.stderr)

    # --- 2. Create the logical flow ---
    result_a = task_a(10)
    result_b = task_b(result_a, 5).with_constraints(gpu=1)

    # --- 3. Instantiate Compiler components ---
    ir_generator = IRGenerator()
    builder = Builder()
    dumper = GraphDumper()

    # --- 4. Run the compilation pipeline ---
    print("Generating IR...", file=sys.stderr)
    graph_ir = ir_generator.generate(result_b)

    # Define a simple environment for the builder
    environment = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=2)])

    print("Building physical graph...", file=sys.stderr)
    physical_graph = builder.build(graph_ir, environment)

    print("Dumping graph to DOT format...", file=sys.stderr)
    dot_string = dumper.to_dot(physical_graph)

    # --- 5. Print the DOT string to stdout ---
    print("\n" + dot_string)

    print("\n--- To generate an image, run: ---", file=sys.stderr)
    print(
        "python examples/dump_graph.py | dot -Tpng -o physical_graph.png",
        file=sys.stderr,
    )
    print("-----------------------------------", file=sys.stderr)


if __name__ == "__main__":
    main()