好的，我们已经成功地完成了 `Cascade` 的 MVP 开发，并通过了所有测试。现在是时候将这些成果作为一个完整的、逻辑一致的工作单元提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划来完成这个任务。

## [COMMIT] feat(core): Implement MVP for declarative task execution engine

### 用户需求
将 `Cascade` MVP 开发阶段的所有文件变更，作为一个完整的特性提交到版本控制中。

### 评论
这个提交标志着 `Cascade` 项目从一个概念到一个可运行的、经过测试的核心产品的转变。我们严格遵循了“洋葱架构”和“API 驱动”的设计原则，构建了一个高度解耦、可观测且易于扩展的基础。特别是在测试策略上的修正，确保了项目的长期健康。

### 目标
1.  将所有新创建和修改的文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git Commit，清晰地记录本次 MVP 开发的所有工作内容和设计决策。

### 基本原理
通过一个原子性的提交来封装整个 MVP 的实现，可以确保版本历史的清晰性。这为后续的功能开发（如阶段二的依赖注入）提供了一个稳定、可靠的基线。

### 标签
#intent/build #flow/ready #priority/critical
#comp/core #comp/runtime #comp/tests
#concept/graph #concept/executor #concept/observability
#task/domain/core #task/object/graph-engine #task/action/initialization
#task/state/end #task/status/completed

---

### Script

#### Acts 1: Stage all changes

我们将所有在 MVP 开发过程中创建和修改的文件添加到 Git 暂存区。

~~~~~act
git_add
~~~~~
~~~~~
pyproject.toml
src/cascade/__init__.py
src/cascade/adapters/__init__.py
src/cascade/adapters/caching/__init__.py
src/cascade/adapters/executors/__init__.py
src/cascade/adapters/executors/local.py
src/cascade/adapters/solvers/__init__.py
src/cascade/adapters/solvers/native.py
src/cascade/graph/__init__.py
src/cascade/graph/build.py
src/cascade/graph/model.py
src/cascade/runtime/__init__.py
src/cascade/runtime/bus.py
src/cascade/runtime/engine.py
src/cascade/runtime/events.py
src/cascade/runtime/protocols.py
src/cascade/runtime/subscribers.py
src/cascade/spec/__init__.py
src/cascade/spec/task.py
tests/test_adapters.py
tests/test_core_mvp.py
tests/test_end_to_end.py
tests/test_runtime_observability.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交，总结 MVP 的所有工作。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement MVP for declarative task execution engine

This commit introduces the minimal viable product for the Cascade library, a declarative, graph-based task execution engine. It provides the core functionality to define tasks with dependencies, build a computation graph, and execute it.

Key components and architectural choices:

1.  **Core Models (`spec`, `graph`):**
    - Implemented a pure, zero-dependency graph model (`Graph`, `Node`).
    - Introduced the user-facing API (`@task`, `LazyResult`) for declaratively defining computation nodes. `LazyResult` acts as a placeholder, enabling the deferred construction of the graph.

2.  **Runtime Engine (`runtime`):**
    - Established an event-driven architecture using a `MessageBus` for high decoupling and observability.
    - The `Engine` class orchestrates the entire workflow: graph building, solving, and execution.
    - A default `HumanReadableLogSubscriber` provides user-friendly console output based on runtime events.

3.  **Adapters (`adapters`):**
    - Following the "Ports and Adapters" pattern, default, zero-dependency implementations for `Solver` and `Executor` are provided.
    - `NativeSolver`: Uses the standard library's `graphlib.TopologicalSorter` to resolve the execution order.
    - `LocalExecutor`: Executes tasks sequentially in the current process.

4.  **Public API (`cascade.run`):**
    - A simple `run()` facade is exposed as the main entry point, hiding the complexity of engine setup.

5.  **Testing Strategy:**
    - Initial end-to-end tests were refactored to validate the emitted event stream from the `MessageBus` rather than asserting against stdout. This aligns the tests with the system's architecture, making them more robust and less coupled to UI details.
~~~~~

### 下一步建议
**Cascade MVP 已正式完成并提交！**

我们已经为 `Cascade` 建立了一个坚实的基础。现在可以满怀信心地进入**阶段二：增强健robustness与可测试性**。

建议的下一个宏观任务是：**实现完整的依赖注入系统**。
我将为这个新任务创建一个 `#task/state/begin` 的计划，其第一个步骤将是：
*   **设计并实现 `@resource` 装饰器和 `cs.inject` 标记**。
