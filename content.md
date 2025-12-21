Excellent, I have the context now. Based on the files, I will proceed with creating a plan to add the necessary tests for our new, more intuitive architecture.

This plan will introduce a new test file for the helper providers and augment the existing graph build tests to validate the deep dependency resolution.

## [WIP] feat: Add smoke tests for deep dependency resolution and helper providers

### 用户需求
Validate the architectural changes made in the previous step by adding comprehensive tests. This includes testing the new `cs.dict` and `cs.format` providers and verifying that `GraphBuilder` now correctly handles nested dependencies within lists and dictionaries.

### 评论
This is a crucial step to solidify the recent refactoring. Adding these tests prevents future regressions and serves as concrete documentation for the new, more intuitive API patterns we've just implemented. It is a high-value action for the project's long-term health and developer experience.

### 目标
1.  Create a new test file `tests/cascade-py/providers/test_helpers.py`.
2.  In this new file, add integration tests for `cs.dict` and `cs.format`, ensuring they correctly resolve `LazyResult` dependencies.
3.  Add a new test case to `tests/cascade-runtime/graph/test_build.py` to specifically validate the recursive dependency discovery within list and dictionary literals.

### 基本原理
We will use `write_file` to create the new test module for the helper providers. These tests will be integration tests that run a small workflow through an `Engine` instance to confirm the providers work end-to-end. For the `GraphBuilder` enhancement, we will use `patch_file` to add a new unit test that constructs a graph with nested dependencies and asserts that all nodes and edges are correctly discovered, thus validating the core of our refactoring.

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/runtime #comp/py #concept/graph #ai/instruct #task/domain/core #task/object/graph-builder #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Create Test File for Helper Providers

First, we'll create a new test file dedicated to the `cs.dict` and `cs.format` providers. These tests will ensure they function correctly within a running engine.

~~~~~act
write_file
tests/cascade-py/providers/test_helpers.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


@pytest.mark.asyncio
async def test_dict_provider():
    @cs.task
    def get_val():
        return "dynamic_value"

    workflow = cs.dict(
        static_key="static",
        dynamic_key=get_val()
    )

    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == {
        "static_key": "static",
        "dynamic_key": "dynamic_value"
    }


@pytest.mark.asyncio
async def test_format_provider():
    @cs.task
    def get_name():
        return "World"

    workflow = cs.format("Hello, {name}!", name=get_name())

    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_format_provider_with_positional_args():
    @cs.task
    def get_first():
        return "first"

    @cs.task
    def get_second():
        return "second"

    workflow = cs.format("Positional: {}, {}", get_first(), get_second())
    
    engine = Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus()
    )
    result = await engine.run(workflow)

    assert result == "Positional: first, second"
~~~~~

#### Acts 2: Add Test for Deep Dependency Resolution

Next, we'll patch the existing `test_build.py` to add a specific test case that validates our new deep dependency discovery logic.

~~~~~act
patch_file
tests/cascade-runtime/graph/test_build.py
~~~~~
~~~~~python
    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert e_node.literal_inputs["name"] == "HOME"
~~~~~
~~~~~python
    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert e_node.literal_inputs["name"] == "HOME"


def test_build_graph_with_nested_dependencies():
    """
    Validates that the GraphBuilder correctly discovers LazyResults
    nested inside lists and dictionaries.
    """
    @cs.task
    def t_a(): return "a"
    @cs.task
    def t_b(): return "b"
    @cs.task
    def t_c(): return "c"

    @cs.task
    def t_main(direct_dep, list_dep, dict_dep):
        return f"{direct_dep}-{list_dep}-{dict_dep}"

    # Create a workflow with nested dependencies
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
    # 3 edges: t_a->t_main, t_b->t_main, t_c->t_main
    assert len(graph.edges) == 3

    node_names = {n.name for n in graph.nodes}
    assert "t_a" in node_names
    assert "t_b" in node_names
    assert "t_c" in node_names
    assert "t_main" in node_names
~~~~~

### 下一步建议
The necessary tests are now defined. The next logical step is to execute the test suite to confirm that our refactoring was successful and that the new providers work as intended. After confirming all tests pass, we can proceed to the final item on our "Architecture 직관화" roadmap: making `cs.inject` failures loud and clear.
