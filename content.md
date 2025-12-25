这是一个完整的、原子化的提交计划，包含了实现“自动汇合语法糖”的所有步骤，以及对核心 API 的兼容性重构。

## [COMMIT] feat(sdk): Implement Auto-Gathering Syntax Sugar for cs.run/visualize/dry_run

### 用户需求
引入自动汇合（Auto-Gathering）语法糖，允许用户直接将一个包含 `LazyResult` 实例的列表或元组传递给 `cs.run`、`cs.visualize` 和 `cs.dry_run`，从而消除并行任务的样板收集代码。

### 评论
这个功能显著提升了开发者体验（DX），使并行任务的声明更加直观，与 Python `asyncio.gather` 的模式保持了一致。通过将该逻辑提升到 `Engine.run` 层面，我们确保了其对所有 Engine 用户和内部测试套件的通用性，同时保持了静态图模型的正确性。

### 目标
1.  在核心 Engine 中实现对 `LazyResult` 列表/元组输入的内部包装。
2.  统一 `cs.run`、`cs.visualize` 和 `cs.dry_run` 的 API，以支持列表输入。
3.  移除所有受影响的测试用例（`test_auto_gathering.py` 等）中的样板 `collect_results` 任务。

### 基本原理
为了实现 API 的高一致性和低侵入性，我们定义了一个 `_internal_gather` 纯任务。当用户传入列表时，我们将其包装为对该纯任务的调用，然后将包装后的 `LazyResult` 传递给图构建器。由于 `_internal_gather` 是纯函数，它不引入性能开销，并完美地模拟了一个聚合节点，从而解决了样板代码问题。

### 标签
#intent/build #flow/done #priority/high
#comp/engine #comp/sdk #comp/tests #scope/api #scope/dx
#ai/instruct
#task/domain/sdk #task/object/auto-gathering #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加/修改所有相关文件到暂存区

~~~~~act
git_add
packages/cascade-sdk/src/cascade/internal/inputs.py
packages/cascade-engine/src/cascade/runtime/engine.py
packages/cascade-sdk/src/cascade/__init__.py
packages/cascade-sdk/src/cascade/tools/visualize.py
packages/cascade-sdk/src/cascade/tools/preview.py
tests/sdk/integration/test_auto_gathering.py
tests/engine/e2e/test_executor_modes.py
tests/engine/e2e/test_offloading.py
tests/sdk/tools/test_visualize.py
tests/sdk/tools/test_preview.py
~~~~~

#### Acts 2: 执行原子提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(sdk): Implement Auto-Gathering Syntax Sugar for cs.run/visualize/dry_run

This change eliminates boilerplate code for collecting results from parallel tasks by allowing users to pass an iterable of LazyResult objects directly to core entrypoint functions.

Key Changes:

1.  **Core Implementation (Engine)**: The auto-gathering logic is moved into `Engine.run` by internally wrapping iterable targets with a new `@task(pure=True)` named `_internal_gather`. This ensures graph compatibility and is applied for all Engine consumers (including tests).
2.  **API Consistency (SDK)**: `cs.run`, `cs.visualize`, and `cs.dry_run` are refactored to accept lists/tuples, unifying the interface across all three key user APIs.
3.  **DX Improvement (Tests)**: Refactored existing e2e tests (`test_executor_modes.py`, `test_offloading.py`) to remove boilerplate `collect_results` tasks, making the tests cleaner and more focused. New TDD tests confirm correct graph construction and execution.

This enhancement significantly improves the usability of Cascade's parallel execution model.
~~~~~
