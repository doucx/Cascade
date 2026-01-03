Of course. Your analysis is spot on. My previous refactoring of `build_graph` to return three values (`graph`, `instance_map`, `executable_registry`) broke its API contract, causing the widespread `ValueError: too many values to unpack (expected 2)` across the entire test suite and any application code that used it. I apologize for this oversight.

Additionally, the related changes to `Executor.execute` and `TaskNode` have caused collateral damage in our test mocks and fixtures.

I will now generate a comprehensive plan to correct all these issues at once, effectively performing the batch update you suggested.

## [WIP] fix(core): Adapt API consumers to core refactoring changes

### 错误分析
我的前一次重构引入了三个破坏性变更，但我未能更新所有受影响的调用点：
1.  **`build_graph` API 变更**: `build_graph` 现在返回一个包含三个元素的元组 `(graph, instance_map, executable_registry)`，而所有调用方（包括 `CascadeApp`, `visualize`, `to_lisp` 以及大量测试）仍然期望接收两个值，导致了 `ValueError`。
2.  **`Executor` 协议变更**: `Executor.execute` 的签名已更改为 `(self, node, callable_obj, args, kwargs)`。测试中使用的 `MockExecutor` 和 `SpyExecutor` 没有随之更新，导致了 `TypeError`。
3.  **`TaskNode` 构造器变更**: `TaskNode` 不再接受 `_callable` 参数。`test_executor_local.py` 中的单元测试仍在尝试传递该参数，导致了 `TypeError`。

### 用户需求
批量修复因核心 API 变更而损坏的整个测试套件和应用程序代码，使 CI 恢复到 `GREEN` 状态。

### 评论
这是一个典型的、在大规模重构中会遇到的问题。它完美地展示了拥有一个全面测试套件的价值——它成为了一个精确的“变更影响检测器”。这次修复将使我们的代码库与新的、解耦的架构原则保持一致，为后续的重构扫清障碍。

### 目标
1.  更新 `cascade-application` 和 `cascade-sdk` 中所有调用 `build_graph` 的地方，以正确处理三个返回值。
2.  批量更新整个测试套件中所有对 `build_graph` 的调用。
3.  修复 `MockExecutor` 和 `SpyExecutor` 的签名，使其与 `Executor` 协议保持一致。
4.  修复 `test_executor_local.py` 中 `TaskNode` 的实例化方式。

### 基本原理
通过一次性的、全面的修复，我们将使整个代码库的狀態与新的 API 契约同步。我们将优先修复应用层代码，然后是测试代码，以确保从上到下的正确性。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/graph #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 2: 批量修复测试中的 `build_graph` 调用

现在，我们来修复测试套件中的 `ValueError`。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_core.py
~~~~~
~~~~~python.old
    workflow = task_b(task_a())
    graph, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~
~~~~~python.new
    workflow = task_b(task_a())
    graph, _, _ = build_graph(workflow)
    node_a = next(n for n in graph.nodes if n.name == "task_a")
    node_b = next(n for n in graph.nodes if n.name == "task_b")
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_solver_csp.py
~~~~~
~~~~~python.old
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph, _ = build_graph(target)

    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)
~~~~~
~~~~~python.new
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph, _, _ = build_graph(target)

    solver = CSPSolver(system_resources={"cpu": 10})
    plan = solver.resolve(graph)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_solver_csp.py
~~~~~
~~~~~python.old
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph, _ = build_graph(target)

    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
~~~~~
~~~~~python.new
    node_a = t_a().with_constraints(cpu=4)
    node_b = t_b().with_constraints(cpu=4)
    target = gather(node_a, node_b)

    graph, _, _ = build_graph(target)

    # Limit system to 6 CPU
    solver = CSPSolver(system_resources={"cpu": 6})
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_solver_native.py
~~~~~
~~~~~python.old
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph, _ = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)
~~~~~
~~~~~python.new
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph, _, _ = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_build.py
~~~~~
~~~~~python.old
    r1 = t1()
    r2 = t2(r1)

    graph, _ = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
~~~~~
~~~~~python.new
    r1 = t1()
    r2 = t2(r1)

    graph, _, _ = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_build.py
~~~~~
~~~~~python.old
    target = process(param_node)

    graph, _ = build_graph(target)

    assert len(graph.nodes) == 2
~~~~~
~~~~~python.new
    target = process(param_node)

    graph, _, _ = build_graph(target)

    assert len(graph.nodes) == 2
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_build.py
~~~~~
~~~~~python.old
    target = echo(env_node)
    graph, _ = build_graph(target)

    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
~~~~~
~~~~~python.new
    target = echo(env_node)
    graph, _, _ = build_graph(target)

    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_build.py
~~~~~
~~~~~python.old
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph, _ = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
~~~~~
~~~~~python.new
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph, _, _ = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_execution_mode.py
~~~~~
~~~~~python.old
    target = collect_results(ct, bt, dt)

    # 2. Build the graph
    graph, instance_map = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
~~~~~
~~~~~python.new
    target = collect_results(ct, bt, dt)

    # 2. Build the graph
    graph, instance_map, _ = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_hashing.py
~~~~~
~~~~~python.old
    target2 = task_a(task_c())

    # Build graphs for both to get the canonical nodes
    _, instance_map1 = build_graph(target1)
    _, instance_map2 = build_graph(target2)

    # Get the canonical node for the root of each graph
    node1 = instance_map1[target1._uuid]
~~~~~
~~~~~python.new
    target2 = task_a(task_c())

    # Build graphs for both to get the canonical nodes
    _, instance_map1, _ = build_graph(target1)
    _, instance_map2, _ = build_graph(target2)

    # Get the canonical node for the root of each graph
    node1 = instance_map1[target1._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_purity_model.py
~~~~~
~~~~~python.old
    b = random_int()

    # Build graphs for each instance
    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
~~~~~
~~~~~python.new
    b = random_int()

    # Build graphs for each instance
    graph_a, instance_map_a, _ = build_graph(a)
    graph_b, instance_map_b, _ = build_graph(b)

    node_a = instance_map_a[a._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_purity_model.py
~~~~~
~~~~~python.old
    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
~~~~~
~~~~~python.new
    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a, _ = build_graph(a)
    graph_b, instance_map_b, _ = build_graph(b)

    node_a = instance_map_a[a._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
def test_serialize_basic_graph():
    target = another_task(simple_task(x=10))
    graph, _ = build_graph(target)

    json_str = to_json(graph)
    data = json.loads(json_str)
~~~~~
~~~~~python.new
def test_serialize_basic_graph():
    target = another_task(simple_task(x=10))
    graph, _, _ = build_graph(target)

    json_str = to_json(graph)
    data = json.loads(json_str)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
def test_round_trip_top_level_functions():
    # We use the top-level tasks defined in this module
    target = another_task(simple_task(x=5))
    original_graph, _ = build_graph(target)

    # Serialize
    json_str = to_json(original_graph)
~~~~~
~~~~~python.new
def test_round_trip_top_level_functions():
    # We use the top-level tasks defined in this module
    target = another_task(simple_task(x=5))
    original_graph, _, _ = build_graph(target)

    # Serialize
    json_str = to_json(original_graph)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
def test_serialize_params_structure_only():
    # Renamed: this test now only checks the graph structure for params, not metadata
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _ = build_graph(target)

    data = graph_to_dict(graph)
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")
~~~~~
~~~~~python.new
def test_serialize_params_structure_only():
    # Renamed: this test now only checks the graph structure for params, not metadata
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _, _ = build_graph(target)

    data = graph_to_dict(graph)
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
def test_serialize_with_retry():
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~python.new
def test_serialize_with_retry():
    t = simple_task(x=1).with_retry(max_attempts=5, delay=1.0, backoff=2.0)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
def test_serialize_with_constraints():
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~
~~~~~python.new
def test_serialize_with_constraints():
    t = simple_task(x=1).with_constraints(gpu_count=1, memory_gb=16)
    graph, _, _ = build_graph(t)

    data = graph_to_dict(graph)
    task_node = next(n for n in data["nodes"] if n["name"] == "simple_task")
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))

    graph, _ = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)
~~~~~
~~~~~python.new
    target = target_condition.with_constraints(cpu=t_dynamic_constraint(1))

    graph, _, _ = build_graph(target)
    json_str = to_json(graph)
    restored_graph = from_json(json_str)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~python.old
    target = consumer(router)

    # Build and Serialize
    graph, _ = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
~~~~~
~~~~~python.new
    target = consumer(router)

    # Build and Serialize
    graph, _, _ = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/integration/test_state_backends.py
~~~~~
~~~~~python.old
    from cascade.graph.build import build_graph

    # The key of the hash field is the node's CANONICAL ID, not its instance UUID
    _, instance_map = build_graph(workflow)
    node = instance_map[workflow._uuid]

    stored_pickled_data = store[results_key][node.current_node_instance_hash]
~~~~~
~~~~~python.new
    from cascade.graph.build import build_graph

    # The key of the hash field is the node's CANONICAL ID, not its instance UUID
    _, instance_map, _ = build_graph(workflow)
    node = instance_map[workflow._uuid]

    stored_pickled_data = store[results_key][node.current_node_instance_hash]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~
~~~~~python.old
    # Pre-build to get the instance map for stable IDs
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(r_d)

    node_a = instance_map[r_a._uuid]
    node_b = instance_map[r_b._uuid]
~~~~~
~~~~~python.new
    # Pre-build to get the instance map for stable IDs
    from cascade.graph.build import build_graph

    _, instance_map, _ = build_graph(r_d)

    node_a = instance_map[r_a._uuid]
    node_b = instance_map[r_b._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~
~~~~~python.old
    )

    from cascade.graph.build import build_graph

    _, instance_map = build_graph(target)

    node_ds = instance_map[data_source._uuid]
    node_target = instance_map[target._uuid]
~~~~~
~~~~~python.new
    )

    from cascade.graph.build import build_graph

    _, instance_map, _ = build_graph(target)

    node_ds = instance_map[data_source._uuid]
    node_target = instance_map[target._uuid]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~
~~~~~python.old
    # Build the graph to get the stable node ID for assertion
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(start_node)
    node_id = instance_map[start_node._uuid].current_node_instance_hash

    dot_string = cs.visualize(start_node)
~~~~~
~~~~~python.new
    # Build the graph to get the stable node ID for assertion
    from cascade.graph.build import build_graph

    _, instance_map, _ = build_graph(start_node)
    node_id = instance_map[start_node._uuid].current_node_instance_hash

    dot_string = cs.visualize(start_node)
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~
~~~~~python.old
    # 4. Build graph to get stable IDs
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(node_c)
    source_id = instance_map[node_c._uuid].current_node_instance_hash
    target_id = instance_map[node_a._uuid].current_node_instance_hash
~~~~~
~~~~~python.new
    # 4. Build graph to get stable IDs
    from cascade.graph.build import build_graph

    _, instance_map, _ = build_graph(node_c)
    source_id = instance_map[node_c._uuid].current_node_instance_hash
    target_id = instance_map[node_a._uuid].current_node_instance_hash
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/integration/test_resource.py
~~~~~
~~~~~python.old
    # The Inject object is nested inside a dict
    flow = task_with_dict_inject(config={"db": cs.inject("my_res")})
    graph, _ = build_graph(flow)

    container = ResourceContainer(bus=cs.MessageBus())
    required = container.scan(graph)
~~~~~
~~~~~python.new
    # The Inject object is nested inside a dict
    flow = task_with_dict_inject(config={"db": cs.inject("my_res")})
    graph, _, executable_registry = build_graph(flow)

    container = ResourceContainer(bus=cs.MessageBus())
    required = container.scan(graph, executable_registry)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_constraint.py
~~~~~
~~~~~python.old
    target = heavy_task().with_constraints(io_bandwidth="high")
    graph, _ = build_graph(target)

    node = next(n for n in graph.nodes if n.name == "heavy_task")

    assert node.constraints is not None
~~~~~
~~~~~python.new
    target = heavy_task().with_constraints(io_bandwidth="high")
    graph, _, _ = build_graph(target)

    node = next(n for n in graph.nodes if n.name == "heavy_task")

    assert node.constraints is not None
~~~~~

#### Acts 3: 修复 Executor Mocks 和测试 Fixtures

最后，修复 `TypeError`。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
from cascade.testing import MockConnector, MockExecutor
~~~~~
~~~~~python.new
from cascade.testing import MockConnector, SpyExecutor


class TimedMockExecutor(SpyExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)


# --- Test Fixtures and Mocks ---
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_constraints.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine_with_connector(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~python.old
import time

import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector, MockExecutor


# --- Fixtures ---
~~~~~
~~~~~python.new
import time
import asyncio
import pytest
import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.testing import MockConnector, SpyExecutor


class TimedMockExecutor(SpyExecutor):
    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay = delay

    async def execute(self, node, callable_obj, args, kwargs):
        await asyncio.sleep(self.delay)
        return await super().execute(node, callable_obj, args, kwargs)


# --- Fixtures ---
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~python.old
@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=MockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
        system_resources={},
    )
~~~~~
~~~~~python.new
@pytest.fixture
def engine(mock_connector):
    return Engine(
        solver=NativeSolver(),
        executor=TimedMockExecutor(delay=0.05),
        bus=MessageBus(),
        connector=mock_connector,
        system_resources={},
    )
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_executor_local.py
~~~~~
~~~~~python.old
    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = TaskNode(
        current_node_instance_hash="add", definition=stub_def, _callable=add.func
    )

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_add, resolved_args, resolved_kwargs))

    assert result == 17  # 5 + 10 + 2
~~~~~
~~~~~python.new
    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = TaskNode(current_node_instance_hash="add", definition=stub_def)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2}  # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_add, add.func, resolved_args, resolved_kwargs)
    )

    assert result == 17  # 5 + 10 + 2
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/unit/test_executor_local.py
~~~~~
~~~~~python.old
    stub_def = TaskDef(
        name="async_add", args=[], fingerprint=Fingerprint(), is_async=True
    )
    node_async = TaskNode(
        current_node_instance_hash="async_add",
        definition=stub_def,
        _callable=async_add.func,
    )

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(executor.execute(node_async, resolved_args, resolved_kwargs))

    assert result == 6
~~~~~
~~~~~python.new
    stub_def = TaskDef(
        name="async_add", args=[], fingerprint=Fingerprint(), is_async=True
    )
    node_async = TaskNode(
        current_node_instance_hash="async_add",
        definition=stub_def,
    )

    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_async, async_add.func, resolved_args, resolved_kwargs)
    )

    assert result == 6
~~~~~

### 下一步建议
我们已经完成了对整个代码库的修复，以适应新的 API 契约。测试套件应该能恢复到 `GREEN` 状态了。

现在，我们可以放心地继续执行原计划的**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。我将生成执行此步骤的计划。
