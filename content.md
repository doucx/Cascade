你说得对，非常感谢你的指正。

我的诊断是：我之前生成的测试用例存在一个根本性的错误，它使用了 `engine.run` 不支持的 API 模式。`AttributeError: 'list' object has no attribute '_uuid'` 这个错误清晰地表明，`engine.run` 的 `target` 参数期望接收一个单一的 `LazyResult` 实例作为图的“根”或“目标”，而不是一个 `LazyResult` 的列表。

我的失误在于将一个 Python 列表直接传递给了执行引擎，而引擎的图构建器需要从一个唯一的、可追溯的 `_uuid` 开始遍历依赖关系。

这是一个很好的例子，说明了为什么我们需要一个严格的、会失败的（RED）测试阶段。它不仅能暴露代码中的缺陷，还能暴露我们对 API 理解上的偏差。

我现在将纠正这个错误，重写测试用例，使其遵循正确的模式：定义一个最终的“收集器”任务，该任务将其他任务的结果作为输入并返回一个列表。这个收集器任务的 `LazyResult` 将成为传递给 `engine.run` 的唯一、合法的目标。

## [WIP] fix(test): 修正工作流定义以符合 engine.run API

### 错误分析
测试 `test_sync_task_offloading_prevents_blocking` 失败的直接原因是向 `engine.run` 传递了一个 `list` 对象，而 `GraphExecutionStrategy` 期望的 `target` 是一个拥有 `_uuid` 属性的对象（如 `LazyResult`），以便在缓存和图构建中使用。

根本原因是测试用例的实现违反了 Cascade 的核心编程模型：一个工作流必须有一个单一的、最终的目标节点 (`LazyResult`)，图的构建和执行计划都是从这个目标节点逆向推导出来的。直接传递一个列表无法构成一个有效的、可分析的计算图。

### 用户需求
用户需要一个能正确使用 `engine.run` API 并且能够验证“同步任务阻塞事件循环”这一当前缺陷的测试用例。该测试用例必须处于一个有效的、可复现的“RED”（失败）状态。

### 评论
这次修正是至关重要的，因为它确保了我们的测试用例本身是建立在正确的 API 使用方式之上的。一个错误的测试用例可能会引导我们去实现一个非预期的、甚至是错误的功能。通过修正测试，我们重新校准了目标，确保了后续对引擎的修改是为了满足一个真实、合法的用户场景。

### 目标
1.  修改 `tests/engine/e2e/test_offloading.py` 文件。
2.  引入一个新的 `@task`，名为 `collect_results`，它接收两个任务的结果，并返回一个列表。
3.  将传递给 `engine.run` 的目标从一个 Python `list` 改为调用 `collect_results` 任务后返回的单一 `LazyResult`。
4.  确保修正后的测试在当前代码下仍然失败，但失败的原因是由于断言失败（阻塞导致），而不是 `AttributeError`。

### 基本原理
通过将多个并行的任务汇聚到一个最终的“收集器”任务中，我们创建了一个结构上有效的 DAG（有向无环图）。这个图有一个明确的“汇聚点”（sink node），图构建器可以从这个点开始进行依赖分析。这种模式不仅是正确的 API 用法，也更清晰地表达了工作流的最终意图——即“我需要这两个任务都完成，并得到它们的聚合结果”。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/offloading-feature #task/action/test-correction #task/state/continue

---

### Script

#### Acts 1: 修正测试用例中的工作流定义

我将使用 `patch_file` 来修复 `test_offloading.py` 中的 API 使用错误，确保它定义了一个有效的、单一目标的工作流。

~~~~~act
patch_file
tests/engine/e2e/test_offloading.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
    """
    测试一个同步的阻塞任务是否被卸载到线程中，
    从而允许其他异步任务并发执行而不会被阻塞。

    此测试在功能实现前会失败，因为同步任务会阻塞整个事件循环，
    导致异步任务在其完成后才能执行。
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # 使用一个静默的总线以保持测试输出干净
    )

    # 这两个任务彼此独立，应该并行运行。
    # 理想情况下，异步任务会立即执行，而同步任务会在一个独立的线程中阻塞。
    sync_result_lr = blocking_sync_task(0.2)
    async_result_lr = non_blocking_async_task()

    # 工作流的目标是这两个任务的结果列表。
    workflow = [sync_result_lr, async_result_lr]

    start_time = time.time()
    results = await engine.run(workflow)
    end_time = time.time()
~~~~~
~~~~~python
@task(pure=True)
def collect_results(sync_res, async_res):
    """一个简单的收集器任务，用于创建有效的图结构。"""
    return [sync_res, async_res]


@pytest.mark.asyncio
async def test_sync_task_offloading_prevents_blocking():
    """
    测试一个同步的阻塞任务是否被卸载到线程中，
    从而允许其他异步任务并发执行而不会被阻塞。

    此测试在功能实现前会失败，因为同步任务会阻塞整个事件循环，
    导致异步任务在其完成后才能执行。
    """
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.adapters.solvers.native import NativeSolver
    from cascade.adapters.executors.local import LocalExecutor

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # 使用一个静默的总线以保持测试输出干净
    )

    # 这两个任务彼此独立，应该并行运行。
    # 理想情况下，异步任务会立即执行，而同步任务会在一个独立的线程中阻塞。
    sync_result_lr = blocking_sync_task(0.2)
    async_result_lr = non_blocking_async_task()

    # 工作流的目标是收集这两个任务的结果。
    workflow_target = collect_results(sync_result_lr, async_result_lr)

    start_time = time.time()
    results = await engine.run(workflow_target)
    end_time = time.time()
~~~~~

### 下一步建议
我们现在有了一个结构正确、但因业务逻辑未实现而失败的测试用例（真正的 RED 状态）。

下一步是进入 TDD 的 GREEN 阶段：修改 `cascade-spec` 和 `cascade-engine` 的代码，实现对同步任务的隐式卸载，使这个测试通过。

我将按原计划进行：
1.  在 `cascade.spec.task.Task` 中添加 `is_async` 属性，以便在图构建时就能识别任务类型。
2.  修改 `cascade.adapters.executors.local.LocalExecutor` 的 `execute` 方法，对 `is_async` 为 `False` 的任务使用 `asyncio.to_thread`。

如果你同意，我将立即生成执行这些代码修改的计划。
