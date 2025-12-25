Excellent. We have successfully reached the "GREEN" state for the auto-gathering feature. Now is the perfect time to refactor existing code to adopt this cleaner syntax, just as you suggested.

Your request to refactor the tests has revealed a valuable architectural improvement. Currently, the auto-gathering logic is only in the high-level, synchronous `cs.run` function. To make this feature available to our asynchronous E2E tests (which build their own `Engine` instance), I will move the logic into the core `Engine.run` method. This makes auto-gathering a more fundamental feature of Cascade and simplifies the `cs.run` function into an even cleaner wrapper.

Based on this, I will refactor `test_executor_modes.py` and also `test_offloading.py` as it follows the same pattern.

However, I will **not** modify `tests/engine/graph/test_execution_mode.py`. This is a deliberate choice because that file is a unit test for the low-level `build_graph` function. `build_graph` correctly and necessarily expects a single `LazyResult` as its root node. Applying the syntax sugar there would mask what the test is designed to verify. We want to keep that test focused on the core graph-building contract.

Here is the plan to perform the refactoring.

## [WIP] refactor: Move auto-gathering to Engine and adopt in tests

### 用户需求
将 `test_executor_modes.py` 和 `test_offloading.py` 中的并行测试样板代码，重构为使用新的自动汇合（auto-gathering）语法。

### 评论
这是一个出色的重构。它不仅清理了测试代码，还促使我们将自动汇合功能从一个简单的 API 语法糖，提升为 `Engine` 的核心特性。这使得该功能对所有 `Engine` 的使用者（包括我们的内部测试套件和高级用户）都可用，从而改善了整体架构。

### 目标
1.  将自动汇合的逻辑从 `cascade.run` 迁移到 `Engine.run` 中。
2.  简化 `cascade.run` 函数，使其直接调用 `Engine.run`。
3.  重构 `tests/engine/e2e/test_executor_modes.py` 和 `tests/engine/e2e/test_offloading.py`，移除 `collect_results` 样板任务，并直接将 `LazyResult` 列表传递给 `engine.run()`。

### 基本原理
通过将列表检测和包装逻辑移入 `Engine.run`，我们确保了 Cascade 的核心行为是一致的，无论它是通过高级 `cs.run` 入口点调用，还是在测试或高级应用中被直接实例化和调用。这遵循了“Don't Repeat Yourself” (DRY) 原则，并使我们的端到端测试能够以更接近用户直觉的方式编写，从而提高了测试代码的可读性和可维护性。

### 标签
#intent/refine #flow/ready #priority/medium #comp/engine #comp/sdk #comp/tests #scope/dx #task/domain/sdk #task/object/auto-gathering #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将自动汇合逻辑移至 `Engine.run`

我们将修改 `Engine` 的 `run` 方法，使其成为处理自动汇合逻辑的中心点。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
~~~~~
~~~~~python
    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = False,
    ) -> Any:
        # Handle Auto-Gathering
        from cascade.internal.inputs import _internal_gather

        if isinstance(target, (list, tuple)):
            if not target:
                return []
            workflow_target = _internal_gather(*target)
        else:
            workflow_target = target

        run_id = str(uuid4())
        start_time = time.time()
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                active_resources: Dict[str, Any] = {}

                final_result = await strategy.execute(
                    target=target,
                    run_id=run_id,
                    params=params or {},
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                )
~~~~~
~~~~~python
                active_resources: Dict[str, Any] = {}

                final_result = await strategy.execute(
                    target=workflow_target,
                    run_id=run_id,
                    params=params or {},
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                )
~~~~~

#### Acts 2: 简化 `cascade.run` 函数

现在 `Engine` 负责处理逻辑，`cs.run` 变成一个非常薄的包装器。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
    # 3. Handle Auto-Gathering
    from .internal.inputs import _internal_gather

    if isinstance(target, (list, tuple)):
        # Handle edge case of empty list
        if not target:
            return []
        # Wrap the iterable in the internal gather task
        workflow_target = _internal_gather(*target)
    else:
        workflow_target = target

    # 4. Assemble the default Engine
    solver = NativeSolver()
~~~~~
~~~~~python
    # 3. Assemble the default Engine
    solver = NativeSolver()
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(workflow_target, params=params))
~~~~~
~~~~~python
        state_backend_factory=sb_factory,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 3: 重构 `test_executor_modes.py`

现在，我们将第一个测试文件更新为使用新的简洁语法。

~~~~~act
patch_file
tests/engine/e2e/test_executor_modes.py
~~~~~
~~~~~python
@task
def collect_results(res1, res2):
    """Aggregates results for a valid graph structure."""
    return res1, res2


@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks():
    """
    Verifies that 'compute' and 'blocking' tasks run in separate thread pools
    and do not block each other.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # A short compute task (0.1s) and a long blocking task (0.2s)
    compute_lr = short_sync_compute_task(0.1)
    blocking_lr = long_sync_blocking_task(0.2)

    # If isolated, compute task finishes at T+0.1s.
    # If not isolated, compute task may have to wait for blocking task, finishing at T+0.2s or later.
    workflow = collect_results(compute_lr, blocking_lr)

    results = await engine.run(workflow)
    compute_finish_time, blocking_finish_time = results

    # The key assertion: the short compute task must finish first.
    assert compute_finish_time < blocking_finish_time, (
        "Compute task should have finished before the blocking task, "
        "indicating parallel execution in separate pools."
    )
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_compute_tasks_are_isolated_from_blocking_tasks():
    """
    Verifies that 'compute' and 'blocking' tasks run in separate thread pools
    and do not block each other.
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # A short compute task (0.1s) and a long blocking task (0.2s)
    compute_lr = short_sync_compute_task(0.1)
    blocking_lr = long_sync_blocking_task(0.2)

    # If isolated, compute task finishes at T+0.1s.
    # If not isolated, compute task may have to wait for blocking task, finishing at T+0.2s or later.
    results = await engine.run([compute_lr, blocking_lr])
    compute_finish_time, blocking_finish_time = results

    # The key assertion: the short compute task must finish first.
    assert compute_finish_time < blocking_finish_time, (
        "Compute task should have finished before the blocking task, "
        "indicating parallel execution in separate pools."
    )
~~~~~

#### Acts 4: 重构 `test_offloading.py`

最后，我们清理第二个测试文件。

~~~~~act
patch_file
tests/engine/e2e/test_offloading.py
~~~~~
~~~~~python
@task(pure=True)
def collect_results(sync_res, async_res):
    """
    Aggregates results to form a single target for the workflow.
    """
    return [sync_res, async_res]


@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
~~~~~
~~~~~act
patch_file
tests/engine/e2e/test_offloading.py
~~~~~
~~~~~python
    # If parallel: Async finishes at T+0.1, Sync at T+0.2
    # If serial: Sync finishes at T+0.2, Async starts then finishes at T+0.3

    workflow_target = collect_results(sync_result_lr, async_result_lr)

    start_time = time.time()
    results = await engine.run(workflow_target)
    end_time = time.time()
~~~~~
~~~~~python
    # If parallel: Async finishes at T+0.1, Sync at T+0.2
    # If serial: Sync finishes at T+0.2, Async starts then finishes at T+0.3

    start_time = time.time()
    results = await engine.run([sync_result_lr, async_result_lr])
    end_time = time.time()
~~~~~

### 下一步建议

我们已经完成了代码和测试的重构。现在是时候将这个功能作为一个完整的逻辑单元进行提交了。我建议生成一个 `[COMMIT]` 计划，将所有相关的修改（TDD 测试、核心实现和重构）包含在一个原子提交中。
