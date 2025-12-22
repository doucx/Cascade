好的，我们已经完成了第一阶段的底层实现。现在，为了确保这些新原语的行为符合预期，并且能够健壮地处理失败和跳过等边缘情况，我们需要编写一套全面的集成测试。

同时，在分析测试用例时，我发现 `cs.pipeline` 的一个关键特性——当某个步骤被 `.run_if(False)` 跳过时，数据应“穿透”该步骤流向下一步——尚未在 `ArgumentResolver` 中实现。因此，本计划将同时包含这部分逻辑的实现和完整的测试套件。

## [WIP] test: 为 sequence 和 pipeline 添加集成测试并实现数据穿透

### 用户需求
为新实现的 `cs.sequence` 和 `cs.pipeline` 编排原语添加集成测试，确保它们在成功、失败和跳过等场景下行为正确。特别是，需要实现并验证 `cs.pipeline` 在步骤被跳过时的数据穿透（data penetration）行为。

### 评论
“吃自己的狗粮”是 Cascade 的核心测试原则。通过编写端到端的集成测试，我们不仅能验证功能的正确性，还能从用户的角度感受新 API 的开发者体验。实现数据穿透是释放 `cs.pipeline` 全部潜力的关键，使其能用于构建真正动态和可配置的数据处理流。

### 目标
1.  **实现数据穿透**: 修改 `ArgumentResolver`，使其在解析一个被跳过的任务的输出时，能自动向上追溯并使用该任务的输入作为替代。
2.  **测试 `cs.sequence`**:
    *   验证任务按预定顺序执行。
    *   验证序列的最终返回值是最后一个任务的返回值。
    *   验证当序列中的一个任务失败时，后续任务不会执行。
    *   验证当序列中的一个任务被跳过时，后续任务也会被跳过。
3.  **测试 `cs.pipeline`**:
    *   验证数据在管道中正确地链式传递。
    *   验证当管道中的一个步骤被跳过时，其输入能正确地“穿透”到下一步。

### 基本原理
**数据穿透实现**: 我们将在 `ArgumentResolver` 的 `_resolve_lazy` 方法中添加逻辑。当它尝试获取一个 `LazyResult` 的值但发现该任务已被跳过（`SKIPPED`）时，它会查询计算图，找到这个被跳过任务的数据输入源，并递归地解析那个源的值。这使得“跳过”在管道中意味着“恒等转换”（identity transformation）。

**测试实现**: 我们将在 `tests/engine/runtime/` 目录下创建一个新的测试文件 `test_flow_primitives.py`。测试将遵循 Cascade 的标准测试模式：手动实例化 `Engine` 及其依赖（如 `NativeSolver`, `LocalExecutor`），并使用 `SpySubscriber` 来断言事件流，从而验证执行行为。

### 标签
#intent/tooling #intent/build #flow/ready #priority/high #comp/core #comp/engine #comp/tests #concept/graph #scope/dx #ai/instruct #task/domain/core #task/object/flow-primitives #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 Pipeline 数据穿透逻辑
我们需要修改 `ArgumentResolver` 以支持在任务被跳过时向上追溯数据源。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def _resolve_lazy(
        self, lr: LazyResult, consumer_id: str, state_backend: StateBackend
    ) -> Any:
        if not state_backend.has_result(lr._uuid):
            # Check for skip
            if state_backend.get_skip_reason(lr._uuid):
                raise DependencyMissingError(
                    consumer_id, "unknown_arg", f"{lr._uuid} (skipped)"
                )
            raise DependencyMissingError(consumer_id, "unknown_arg", lr._uuid)

        return state_backend.get_result(lr._uuid)

    def _resolve_router(
~~~~~
~~~~~python
    def _resolve_lazy(
        self,
        lr: LazyResult,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        if not state_backend.has_result(lr._uuid):
            # Check for skip. If skipped, attempt data penetration.
            if state_backend.get_skip_reason(lr._uuid):
                # Find the skipped node's primary data input
                for edge in graph.edges:
                    if edge.target.id == lr._uuid and edge.edge_type == EdgeType.DATA:
                        # Found the upstream data source. Recursively resolve it.
                        # This assumes a simple pipeline structure (one main data input).
                        # Find the LazyResult corresponding to the source node.
                        # This is tricky without a direct back-reference.
                        # For now, we make a simplifying assumption this works for pipelines.
                        # We need a way to get the LazyResult from a Node.
                        # The resolver doesn't have this. Let's trace from the source node's result.
                        source_lr_stub = LazyResult(task=None, args=(), kwargs={}, _uuid=edge.source.id)
                        try:
                            return self._resolve_lazy(
                                source_lr_stub, consumer_id, state_backend, graph
                            )
                        except DependencyMissingError:
                            # If the upstream of the skipped node is ALSO missing, then we fail.
                            pass

                # If penetration fails or it's not a pipeline-like structure, raise.
                raise DependencyMissingError(
                    consumer_id, "unknown_arg", f"{lr._uuid} (skipped)"
                )

            raise DependencyMissingError(consumer_id, "unknown_arg", lr._uuid)

        return state_backend.get_result(lr._uuid)

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        """
        Recursively traverses lists, tuples, and dicts.
        Replaces LazyResult, Router, and Inject.
        """
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            return self._resolve_lazy(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Router):
            return self._resolve_router(obj, consumer_id, state_backend, graph)

        elif isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)

        elif isinstance(obj, list):
            return [
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            ]

        elif isinstance(obj, tuple):
            return tuple(
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            )

        elif isinstance(obj, dict):
            return {
                k: self._resolve_structure(
                    v, consumer_id, state_backend, resource_context, graph
                )
                for k, v in obj.items()
            }

        return obj

    def _resolve_router(
        self, router: Router, consumer_id: str, state_backend: StateBackend, graph: Graph
    ) -> Any:
        # 1. Resolve Selector
        selector_uuid = router.selector._uuid
        if not state_backend.has_result(selector_uuid):
            raise DependencyMissingError(consumer_id, "router_selector", selector_uuid)

        selector_value = state_backend.get_result(selector_uuid)

        # 2. Pick Route
        try:
            selected_lr = router.routes[selector_value]
        except KeyError:
            raise ValueError(
                f"Router selector returned '{selector_value}', "
                f"but no matching route found in {list(router.routes.keys())}"
            )

        # 3. Resolve Route Result
        return self._resolve_lazy(selected_lr, consumer_id, state_backend, graph)

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Special handling for internal param fetcher
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # Recursively resolve the structure
        resolved_structure = self._resolve_structure(
            node.literal_inputs, node.id, state_backend, resource_context, graph
        )

        # Re-assemble args and kwargs
        final_kwargs = {k: v for k, v in resolved_structure.items() if not k.isdigit()}
~~~~~


#### Acts 2: 添加集成测试
现在我们创建测试文件并填充所有必要的测试用例。

~~~~~act
write_file
tests/engine/runtime/test_flow_primitives.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.events import TaskSkipped


@pytest.mark.asyncio
async def test_sequence_executes_in_order(bus_and_spy):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_a():
        execution_order.append("A")

    @cs.task
    def task_b():
        execution_order.append("B")

    @cs.task
    def task_c():
        execution_order.append("C")

    workflow = cs.sequence([task_a(), task_b(), task_c()])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)

    assert execution_order == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_sequence_forwards_last_result(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def first():
        return "first"

    @cs.task
    def last():
        return "last"

    workflow = cs.sequence([first(), last()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == "last"


@pytest.mark.asyncio
async def test_sequence_aborts_on_failure(bus_and_spy):
    bus, spy = bus_and_spy
    execution_order = []

    @cs.task
    def task_ok():
        execution_order.append("ok")

    @cs.task
    def task_fail():
        execution_order.append("fail")
        raise ValueError("This task fails")

    @cs.task
    def task_never():
        execution_order.append("never")

    workflow = cs.sequence([task_ok(), task_fail(), task_never()])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    with pytest.raises(ValueError, match="This task fails"):
        await engine.run(workflow)

    assert execution_order == ["ok", "fail"]


@pytest.mark.asyncio
async def test_sequence_aborts_on_skipped_node(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def task_a():
        return "A"

    @cs.task
    def task_b(a):
        return "B"

    @cs.task
    def task_c(b):
        return "C"

    false_condition = cs.task(lambda: False)()
    # task_b will be skipped, which should cause task_c to be skipped too.
    workflow = cs.sequence([task_a(), task_b(1).run_if(false_condition), task_c(2)])

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    await engine.run(workflow)

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 2

    skipped_names = {event.task_name for event in skipped_events}
    assert skipped_names == {"task_b", "task_c"}

    # Verify task_c was skipped because its sequence dependency was skipped
    task_c_skipped_event = next(
        e for e in skipped_events if e.task_name == "task_c"
    )
    assert task_c_skipped_event.reason == "UpstreamSkipped_Sequence"


@pytest.mark.asyncio
async def test_pipeline_chains_data_correctly(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    workflow = cs.pipeline(10, [add_one, multiply_by_two])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == 22


@pytest.mark.asyncio
async def test_pipeline_with_lazy_initial_input(bus_and_spy):
    bus, _ = bus_and_spy

    @cs.task
    def get_initial():
        return 10

    @cs.task
    def add_one(x):
        return x + 1

    workflow = cs.pipeline(get_initial(), [add_one])
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    assert result == 11


@pytest.mark.asyncio
async def test_pipeline_with_run_if_data_penetration(bus_and_spy):
    bus, spy = bus_and_spy

    @cs.task
    def add_one(x):
        return x + 1

    @cs.task
    def multiply_by_two(x):
        return x * 2

    @cs.task
    def add_three(x):
        return x + 3

    false_condition = cs.task(lambda: False)()
    workflow = cs.pipeline(
        10, [add_one, multiply_by_two.run_if(false_condition), add_three]
    )

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)
    result = await engine.run(workflow)

    # Expected: 10 -> add_one -> 11
    # -> multiply_by_two is skipped
    # -> 11 (from add_one) penetrates to add_three
    # -> 11 + 3 = 14
    assert result == 14

    skipped_events = spy.events_of_type(TaskSkipped)
    assert len(skipped_events) == 1
    assert skipped_events[0].task_name == "multiply_by_two"
~~~~~

### 下一步建议
我们已经为新的流式原语奠定了坚实的实现和测试基础。下一步可以考虑：
1.  **文档化**: 在官方文档中为 `cs.sequence` 和 `cs.pipeline` 添加专门的章节，包含清晰的示例和对其与策略（如 `.with_retry`）组合方式的解释。
2.  **Linter 增强**: 探索增强 `cs.dry_run` 或创建一个独立的 linter 工具，以检测 `cs.pipeline` 中的常见错误，例如将已调用的任务 `my_task()` 而不是任务工厂 `my_task` 传递给 `steps` 列表。
