#!/usr/bin/env python3
"""
Dump Physical Graph Example

This script demonstrates how to use the Cascade Compiler and GraphDumper
to generate a visual representation (DOT format) of the underlying physical topology.

It constructs a scenario where two tasks compete for a single GPU resource,
resulting in a complex physical graph involving Resource Brokers, Requestors, and Buffers.

Usage:
    python examples/dump_physical_graph.py > graph.dot
    dot -Tpng graph.dot -o graph.png
"""

import os
import sys

# Ensure we can import packages from the workspace
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-spec/src")
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-compiler/src")
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../packages/cascade-common/src")
    ),
)
# Add other packages if needed, but these should cover the compiler deps

from cascade.compiler.backend.builder import Builder
from cascade.compiler.utils.visualizer import GraphDumper
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.ir.graph import ArgumentDef, ArgumentKind, GraphIR, NodeIR, TaskDef
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef


def main():
    print("# Building GraphIR...", file=sys.stderr)

    # 1. Define a dummy task definition
    # We use a static fingerprint for reproducibility
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc12345"})
    task_def = TaskDef(
        name="gpu_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )

    # 2. Create two nodes that both require 1 GPU
    node_1 = NodeIR(
        current_node_instance_hash="node_1",
        name="TrainingJob_A",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        current_node_instance_hash="node_2",
        name="TrainingJob_B",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 3. Define the Environment (Constraint Boundary)
    # Only 1 GPU is available globally
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])

    print("# Compiling to Physical Bipartite Graph...", file=sys.stderr)
    builder = Builder()
    artifact = builder.build(graph_ir, environment=env)
    physical_graph = artifact.assembly.graph

    node_count = len(physical_graph.nodes)
    channel_count = len(physical_graph.channels)
    print(
        f"# Generated Physical Graph: {node_count} nodes, {channel_count} channels",
        file=sys.stderr,
    )

    # 4. Dump to DOT
    print("# Generating DOT output...", file=sys.stderr)
    dumper = GraphDumper()
    dot_output = dumper.to_dot(physical_graph)

    # Print DOT to stdout so it can be piped
    print(dot_output)


if __name__ == "__main__":
    main()
