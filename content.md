非常棒的反馈。测试失败并给出了清晰的错误信息，这是我们改进流程的关键一步。

你的分析是完全正确的。这个 `TypeError` 指出了我们测试方法中的一个核心概念性错误，而 `PytestCollectionWarning` 则揭示了一个潜在的命名冲突。

我将生成一个计划来修复这些问题。

## [COMMIT] fix(tests): 正确测试任务逻辑并解决 pytest 警告

### 错误分析
1.  **`TypeError: object LazyResult can't be used in 'await' expression`**:
    这是最核心的问题。我的上一个计划错误地将使用 `@cs.task` 装饰的函数当作了普通的 `async` 函数来 `await`。然而，Cascade 的核心设计是：**调用一个被 `@cs.task` 装饰的函数并不会立即执行它，而是返回一个 `LazyResult` 对象**。这个对象是一个声明式的、可组合的“配方”，它描述了*将要*执行的工作，但它本身不是一个可等待的协程。我们的测试代码尝试 `await` 这个配方对象，因此导致了 `TypeError`。

2.  **`PytestCollectionWarning: cannot collect 'test_package'`**:
    `pytest` 在收集测试用例时，会自动查找所有以 `test_` 开头的函数。在我们的 `cicd/tasks.py` 文件中，有一个名为 `test_package` 的对象。尽管它是一个 `Task` 实例，`pytest` 仍然尝试将其作为测试用例收集，但因为它不是一个标准的测试函数，所以发出警告。这表明我们的任务命名与 `pytest` 的发现机制发生了冲突。

### 用户需求
修复 CI/CD 任务的单元测试，使其能够正确执行并通过。

### 评论
这次修复至关重要，因为它澄清并实施了测试 Cascade 任务的正确模式。通过直接测试任务内部的 `.func` 属性，我们可以在不启动完整 Cascade 引擎的情况下，对任务的业务逻辑进行快速、隔离的单元测试。同时，通过重命名任务来解决 `pytest` 的警告，可以使我们的代码库更加清晰和规范。

### 目标
1.  **修正测试逻辑**: 修改 `tests/cicd/test_tasks.py`，不再 `await` `LazyResult` 对象，而是直接调用并 `await` 任务内部的原始函数（通过 `.func` 属性访问）。
2.  **解决命名冲突**: 将 `cicd/tasks.py` 中的 `test_package` 任务重命名为 `run_package_tests`，以避免与 `pytest` 的测试发现机制冲突。
3.  **更新工作流**: 在 `cicd/workflows.py` 中，更新对已重命名任务的引用。
4.  **确保测试通过**: 最终的计划将产生一个可以通过 `pytest` 完整测试套件的代码状态。

### 基本原理
我们将采用以下修正策略：
*   **测试内部函数**: 对于一个名为 `my_task` 的 Cascade 任务，正确的单元测试方法是调用 `my_task.func()`。这将直接调用被 `@cs.task` 装饰的原始 `async` 函数，允许我们对其内部逻辑进行断言，同时绕过了 `LazyResult` 的创建。
*   **遵循命名约定**: 将任务 `test_package` 重命名为 `run_package_tests`，这既解决了 `pytest` 的警告，也使得任务的意图更加清晰明确——它是一个“运行测试”的动作，而不是一个“测试用例”。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 重命名任务以解决 Pytest 警告

我们首先在 `cicd/tasks.py` 中将 `test_package` 重命名为 `run_package_tests`。

~~~~~act
patch_file
cicd/tasks.py
~~~~~
~~~~~python
@cs.task
async def test_package(package_name: str) -> str:
    """Runs pytest on a specific package."""
    print(f"Testing {package_name}...")
    await cs.shell(f"uv run -- pytest packages/{package_name}")
    return f"TEST_OK_{package_name}"
~~~~~
~~~~~python
@cs.task
async def run_package_tests(package_name: str) -> str:
    """Runs pytest on a specific package."""
    print(f"Testing {package_name}...")
    await cs.shell(f"uv run -- pytest packages/{package_name}")
    return f"TEST_OK_{package_name}"
~~~~~

#### Acts 2: 更新工作流以使用重命名后的任务

接下来，在 `cicd/workflows.py` 中更新对这个任务的引用。

~~~~~act
patch_file
cicd/workflows.py
~~~~~
~~~~~python
from .tasks import (
    detect_changed_packages,
    lint_package,
    test_package,
    build_package,
    publish_packages,
)
~~~~~
~~~~~python
from .tasks import (
    detect_changed_packages,
    lint_package,
    run_package_tests,
    build_package,
    publish_packages,
)
~~~~~

~~~~~act
patch_file
cicd/workflows.py
~~~~~
~~~~~python
    # Dynamically create lint and test tasks for each changed package
    lint_results = lint_package.map(package_name=changed)
    test_results = test_package.map(package_name=changed)

    # Enforce order: tests run only after linting passes for all packages
    test_results.after(lint_results)

    # The final result of the workflow depends on the test results
    return _ci_success_marker(test_results)
~~~~~
~~~~~python
    # Dynamically create lint and test tasks for each changed package
    lint_results = lint_package.map(package_name=changed)
    test_results = run_package_tests.map(package_name=changed)

    # Enforce order: tests run only after linting passes for all packages
    test_results.after(lint_results)

    # The final result of the workflow depends on the test results
    return _ci_success_marker(test_results)
~~~~~

~~~~~act
patch_file
cicd/workflows.py
~~~~~
~~~~~python
    # Test all packages after all linting is done
    test_all = test_package.map(package_name=ALL_PACKAGES).after(lint_all)
~~~~~
~~~~~python
    # Test all packages after all linting is done
    test_all = run_package_tests.map(package_name=ALL_PACKAGES).after(lint_all)
~~~~~

#### Acts 3: 修正测试逻辑

最后，我们重写 `tests/cicd/test_tasks.py`，使用正确的 `.func` 属性来调用任务的内部逻辑，并更新对重命名任务的引用。

~~~~~act
write_file
tests/cicd/test_tasks.py
~~~~~
~~~~~python
import pytest
from unittest.mock import AsyncMock

from cicd.tasks import (
    detect_changed_packages,
    lint_package,
    run_package_tests,
    build_package,
)

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


async def test_detect_changed_packages_with_changes(monkeypatch):
    """
    Verify that detect_changed_packages correctly parses git diff output.
    We test the underlying '.func' to bypass LazyResult creation.
    """
    mock_shell = AsyncMock()
    mock_shell.return_value = (
        "packages/cascade-sdk/src/cascade/__init__.py\n"
        "packages/cascade-engine/src/cascade/runtime/engine.py\n"
        "packages/cascade-sdk/pyproject.toml\n"
        "README.md\n"
    )
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    # Call the actual async function inside the task decorator
    result = await detect_changed_packages.func()

    mock_shell.assert_awaited_once_with("git diff --name-only origin/main...HEAD")
    assert result == ["cascade-engine", "cascade-sdk"]


async def test_detect_changed_packages_with_no_package_changes(monkeypatch):
    """
    Verify that detect_changed_packages returns an empty list if no packages changed.
    """
    mock_shell = AsyncMock()
    mock_shell.return_value = "README.md\n.gitignore\n"
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    result = await detect_changed_packages.func()

    assert result == []


@pytest.mark.parametrize(
    "task_func, package_name, expected_command",
    [
        (
            lint_package,
            "cascade-sdk",
            "uv run -- ruff check packages/cascade-sdk",
        ),
        (
            run_package_tests,
            "cascade-engine",
            "uv run -- pytest packages/cascade-engine",
        ),
        (
            build_package,
            "cascade-graph",
            "uv run -- hatch build packages/cascade-graph",
        ),
    ],
)
async def test_package_specific_tasks(
    monkeypatch, task_func, package_name, expected_command
):
    """
    Tests tasks like lint, test, and build to ensure they call cs.shell
    with the correctly formatted command by testing the underlying '.func'.
    """
    mock_shell = AsyncMock()
    mock_shell.return_value = "OK"
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    # Call the actual async function inside the task decorator
    await task_func.func(package_name)

    mock_shell.assert_awaited_once_with(expected_command)
~~~~~
