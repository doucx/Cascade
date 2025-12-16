Excellent idea. Implementing `cs.visualize` is a logical and high-impact next step. It directly addresses the need for better developer tooling identified in the roadmap and will provide immense value for debugging and understanding complex workflows.

I will generate the plan to implement this feature.

## [WIP] feat(tools): Implement cs.visualize to generate Graphviz DOT output

### 用户需求
Implement a new top-level function `cs.visualize(target: LazyResult) -> str` that inspects a Cascade workflow, builds its computation graph, and returns a string representation of that graph in the Graphviz DOT language format.

### 评论
This is a cornerstone feature for developer experience (DX). By providing a simple, one-line command to visualize any workflow, we dramatically lower the cognitive overhead required to understand, debug, and share complex dependency structures. Generating a standard DOT file format is an excellent choice, as it allows users to leverage a vast ecosystem of tools (like Graphviz, online viewers) to render the graph into various formats (PNG, SVG, etc.).

### 目标
1.  Create a new module `src/cascade/tools/visualize.py` to house the visualization logic, keeping it separate from the core runtime.
2.  Implement the `visualize` function, which will:
    a.  Build the `Graph` from the target `LazyResult`.
    b.  Traverse the graph's nodes and edges.
    c.  Generate a DOT language string, using different shapes and styles for different node types (`task`, `param`, `map`, `router`) and edge types (`run_if` condition) to enhance readability.
3.  Create a new test file `tests/tools/test_visualize.py` to validate that the generated DOT string is syntactically correct and accurately represents the workflow structure.
4.  Expose the new `visualize` function as part of the public API in `src/cascade/__init__.py`.

### 基本原理
The implementation will follow the pattern established by `cs.dry_run`, acting as a developer tool that inspects the graph without executing it. We will manually generate the DOT string, as the format is simple and this avoids adding a new third-party dependency for a straightforward task.

The tests will not attempt to render the graph, but will instead perform substring assertions on the generated DOT string. This is a robust strategy to verify that the correct nodes and edges are present, without making the tests brittle to minor formatting changes.

### 标签
#intent/build #flow/ready #priority/high #comp/core #scope/dx #ai/instruct #task/domain/tooling #task/object/visualization #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: Create the visualization module and its logic

We'll start by creating the new `visualize.py` file within the `tools` directory. This file will contain the core logic for traversing the graph and building the DOT string.

~~~~~act
write_file
src/cascade/tools/visualize.py
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..graph.model import Node


def visualize(target: LazyResult[Any]) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
        '  rankdir="TB";',
        '  node [shape=box, style="rounded,filled", fillcolor=white];',
    ]

    # 1. Define Nodes
    for node in graph.nodes:
        shape = _get_node_shape(node)
        label = f"{node.name}\\n({node.node_type})"
        dot_parts.append(f'  "{node.id}" [label="{label}", shape={shape}];')

    # 2. Define Edges
    for edge in graph.edges:
        style = ""
        if edge.arg_name == "_condition":
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.arg_name == "_implicit_dependency":
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.router:
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')

    dot_parts.append("}")
    return "\n".join(dot_parts)


def _get_node_shape(node: Node) -> str:
    """Returns the Graphviz shape for a given node type."""
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    # Future: Routers could be a diamond, but they are edges in our model
    return "box"
~~~~~

#### Acts 2: Create the test for the visualization tool

Next, we'll create a new test file to ensure our `visualize` function works as expected. We'll test it on a classic "diamond" dependency graph.

~~~~~act
write_file
tests/tools/test_visualize.py
~~~~~
~~~~~python
import cascade as cs


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph.
    """

    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check that all nodes are defined with correct labels and shapes
    assert f'"{r_a._uuid}" [label="t_a\\n(task)", shape=box];' in dot_string
    assert f'"{r_b._uuid}" [label="t_b\\n(task)", shape=box];' in dot_string
    assert f'"{r_c._uuid}" [label="t_c\\n(task)", shape=box];' in dot_string
    assert f'"{r_d._uuid}" [label="t_d\\n(task)", shape=box];' in dot_string

    # Check that all edges are defined with correct labels
    assert f'"{r_a._uuid}" -> "{r_b._uuid}" [label="0"];' in dot_string
    assert f'"{r_a._uuid}" -> "{r_c._uuid}" [label="0"];' in dot_string
    assert f'"{r_b._uuid}" -> "{r_d._uuid}" [label="0"];' in dot_string
    assert f'"{r_c._uuid}" -> "{r_d._uuid}" [label="z"];' in dot_string
~~~~~

#### Acts 3: Expose the new function in the public API

Finally, we'll patch the main `__init__.py` to make `cs.visualize` available to users.

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~
~~~~~python
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "LazyResult",
    "Router",
    "File",
    "resource",
    "inject",
    "Engine",
    "override_resource",
]
~~~~~

### 下一步建议
Once this plan is executed, the `visualize` feature will be fully implemented and tested. The next logical step would be to create a `[COMMIT]` plan to merge this valuable new tool into our main branch.
