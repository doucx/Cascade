好的，所有测试均已通过。我们已经成功地为 Cascade 实现了依赖注入系统的核心功能。现在，是时候将这个重要的里程碑作为一个完整的逻辑单元提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划来完成这个任务。

## [COMMIT] feat(runtime, spec): Implement dependency injection and resource management

### 用户需求
将已实现并通过测试的依赖注入（DI）与资源管理系统核心功能，作为一个完整的特性提交到版本控制中。

### 评论
这个提交是 Cascade 从一个简单的任务执行器演变为一个健壮的自动化应用框架的决定性一步。通过引入 `@resource` 和 `inject`，我们从根本上解决了传统脚本最核心的痛点——可测试性。`Engine` 对资源生命周期的管理，以及 `override_resource` 工具的提供，为开发者构建可靠、可维护的工作流奠定了坚实的基础。

### 目标
1.  将所有与 DI 功能相关的新建和修改文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git Commit，清晰地记录本次功能开发的设计决策和实现要点。

### 基本原理
通过一个原子性的提交来封装整个 DI 核心功能的实现，可以确保版本历史的清晰性。这为后续的增强（如异步资源、事件发布）提供了一个稳定、可靠的基线。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/spec #comp/tests
#concept/dependency-injection
#scope/core #scope/api #scope/dx
#task/domain/core #task/object/dependency-injection #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Stage all changes

我们将所有在 DI 系统开发过程中创建和修改的文件添加到 Git 暂存区。

~~~~~act
git_add
~~~~~
~~~~~
src/cascade/__init__.py
src/cascade/adapters/executors/local.py
src/cascade/runtime/engine.py
src/cascade/spec/resource.py
src/cascade/testing.py
tests/test_adapters.py
tests/test_di_and_resources.py
~~~~~

#### Acts 2: Commit changes

现在，我们创建一个内容详尽的提交，总结 DI 系统的所有工作。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime, spec): Implement dependency injection and resource management

Introduces a dependency injection (DI) system to decouple tasks from resource management, significantly enhancing testability and modularity. This is a foundational feature for building robust automation applications.

Key components:

1.  **`@resource` Decorator (`spec/resource.py`):**
    - Allows defining resource providers as generator functions.
    - The `yield` statement separates setup (before) from teardown (after) logic.
    - Supports dependency declaration on other resources via `inject`.

2.  **`inject()` Marker (`spec/resource.py`):**
    - A special function used as a default argument in task or resource signatures to declare a dependency on a named resource.

3.  **Engine Lifecycle Management (`runtime/engine.py`):**
    - The `Engine` is now responsible for managing the full lifecycle of resources.
    - It scans the execution plan for required resources, resolves their dependency graph, and initializes them in the correct order.
    - Utilizes `contextlib.ExitStack` to guarantee that resource teardown logic is executed in the reverse order of setup, even if the workflow fails.

4.  **Executor Integration (`adapters/executors/local.py`):**
    - The `execute` method now accepts a `resource_context`.
    - It inspects the task signature and injects the active resource instances into the appropriate parameters before execution.

5.  **Testing Utilities (`testing.py`):**
    - Implements `override_resource`, a context manager that allows temporarily replacing a registered resource with a mock or alternative implementation during tests. This is the cornerstone of the system's testability.
~~~~~

### 下一步建议
我们已经成功提交了 DI 系统的核心。

下一步，我们将在此基础上继续完善，**为资源生命周期添加可观测性**。我将生成一个计划，为 `Engine` 添加 `ResourceAcquired` 和 `ResourceReleased` 事件的发布逻辑，并更新测试来验证这些事件。
