You are absolutely right. My apologies.

My analysis of the `build_graph` function's behavior was incorrect. The error message `TypeError: Cannot build graph from type <class 'list'>` clearly shows that `build_graph`, just like `engine.run`, requires a single `LazyResult` as its entry point to begin the traversal. My assumption that it could accept an iterable was wrong.

This is another excellent demonstration of the TDD process catching flawed assumptions, even in the test code itself. Thank you for the correction.

I will now fix the test by using the same "collector" pattern we established previously. This will create a valid, single-target graph for the builder to analyze. Since the underlying code changes for propagating the `mode` were likely correct, this fix should result in a passing test.

## [WIP] fix(test): Correct GraphBuilder API usage in test

### 错误分析
The test `test_execution_mode_is_passed_to_node` failed with a `TypeError` because the `build_graph` function was called with a `list` of `LazyResult` objects. The `GraphBuilder`'s internal `_visit` method is designed to start its traversal from a single object (`LazyResult` or `MappedLazyResult`) and does not know how to handle an iterable. My previous note in the test code, stating that `build_graph` could accept a list, was fundamentally incorrect.

### 用户需求
The user needs a test that correctly uses the `build_graph` API to verify that the `mode` parameter from the `@task` decorator is successfully propagated to the `execution_mode` attribute on the `Node` object.

### 评论
This correction is crucial for maintaining the integrity of our test suite. A test that uses the API incorrectly provides no value and can mask real issues. By fixing this test, we ensure that we are validating our feature against the correct, intended usage pattern of the framework's core components.

### 目标
1.  Modify `tests/engine/graph/test_execution_mode.py`.
2.  Introduce a `collect_results` task to aggregate multiple `LazyResult` objects into a single, valid graph target.
3.  Update the call to `build_graph` to pass the single `LazyResult` from the new collector task.
4.  Ensure the corrected test passes, thus confirming the feature's implementation is correct.

### 基本原理
A valid, analyzable computation graph must have a clear structure with defined dependencies. By channeling multiple parallel tasks into a single collector task, we create a Directed Acyclic Graph (DAG) with a single "sink" node. This provides the `GraphBuilder` with the necessary single entry point to begin its dependency traversal and correctly construct the graph model.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/graph #scope/dx #ai/instruct #task/domain/testing #task/object/graph-builder-api #task/action/test-correction #task/state/continue

---

### Script

#### Acts 1: Fix the test case API usage

I will patch the test to use the collector pattern, providing a valid single target to `build_graph`.

~~~~~act
patch_file
tests/engine/graph/test_execution_mode.py
~~~~~
~~~~~python
def test_execution_mode_is_passed_to_node():
    """
    Verifies that the `mode` parameter from the @task decorator
    is correctly propagated to the `execution_mode` attribute of the
    corresponding Node in the graph.
    """
    # 1. Define a simple workflow
    ct = compute_task()
    bt = blocking_task()
    dt = default_task()

    # We need a target to build the graph
    target = [ct, bt, dt]

    # 2. Build the graph
    # NOTE: We are building from a list, which is not a valid final target for
    # the engine, but it is sufficient for build_graph to explore all dependencies.
    # The build_graph function does not require a single root LazyResult.
    graph, instance_map = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
~~~~~
~~~~~python
@task
def collect_results(c, b, d):
    return [c, b, d]


def test_execution_mode_is_passed_to_node():
    """
    Verifies that the `mode` parameter from the @task decorator
    is correctly propagated to the `execution_mode` attribute of the
    corresponding Node in the graph.
    """
    # 1. Define a simple workflow
    ct = compute_task()
    bt = blocking_task()
    dt = default_task()

    # Create a single target that depends on all other tasks
    target = collect_results(ct, bt, dt)

    # 2. Build the graph
    graph, instance_map = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
~~~~~

### 下一步建议
We have now corrected the faulty test case. Please run the tests again.

I expect `tests/engine/graph/test_execution_mode.py` to **pass** this time. A passing result will confirm that the code modifications from the previous step were indeed correct and that the `mode` parameter is now successfully being passed from the `@task` decorator all the way to the `Node` object in the graph.

Once this is confirmed, we can confidently proceed to **Phase 2**: implementing the dedicated thread pool logic in `LocalExecutor`.
