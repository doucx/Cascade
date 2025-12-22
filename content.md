Excellent. The next logical step is to build a test suite for our new `cicd/` logic. This is the primary benefit of our "CI as code" approach: we can write robust, isolated, and fast unit tests for our pipeline logic, something that is nearly impossible with traditional YAML-based CI.

I will create the necessary test files and implement mock-based unit tests for the tasks defined in `cicd/tasks.py`. This will ensure our core logic is verifiable and correct, independent of external tools like `git` or `ruff`.

## [WIP] test: Add unit tests for CI/CD tasks

### 用户需求
为新创建的 `cicd/` 目录下的任务逻辑创建一个基础的、无错误的 `pytest` 测试套件。

### 评论
这是将 CI/CD 作为应用程序来构建的核心优势的体现。通过为我们的 CI/CD 任务编写单元测试，我们确保了其逻辑的健壮性和可维护性。使用 Mocking 技术，我们可以将任务的内部逻辑（例如，解析 `git diff` 的输出）与外部依赖（实际执行 `git` 命令）完全解耦，从而实现快速、可靠的测试。

### 目标
1.  **创建测试目录结构**: 建立 `tests/cicd/` 目录以匹配我们的源代码结构。
2.  **创建测试文件**: 添加 `tests/cicd/test_tasks.py` 文件。
3.  **实现对 `detect_changed_packages` 的测试**: 使用 `monkeypatch` 和 `AsyncMock` 来模拟 `cs.shell("git diff ...")` 的调用，并验证我们的解析逻辑是否能正确地从模拟输出中提取出变更的包名。
4.  **实现对其他原子任务的测试**: 为 `lint_package`、`test_package` 和 `build_package` 等任务创建参数化的测试，验证它们是否生成了正确的 shell 命令字符串并传递给 `cs.shell`。
5.  **确保测试套件通过**: 保证新添加的测试在当前代码基础上可以无错误地通过。

### 基本原理
我们将严格遵循“验证意图而非实现”的测试原则 (`d3-principle-python-testing-mock-intent`)。所有与外部 shell 命令交互的任务都将通过 `pytest` 的 `monkeypatch` fixture 进行测试。

*   对于 `detect_changed_packages`，测试的重点是验证其**解析逻辑**。我们将模拟 `cs.shell` 以返回一个预定义的、多行的 `git diff` 输出字符串，然后断言该函数能否正确地解析这个字符串并返回预期的包名列表。
*   对于 `lint_package` 等任务，测试的重点是验证其**命令构建逻辑**。我们将断言 `cs.shell` 被以一个**正确格式化的命令字符串**（例如 `uv run -- ruff check packages/cascade-sdk`）调用。

这种方法使得我们的测试既快速又不依赖于文件系统或外部工具链的状态，从而保证了 CI 流程本身的稳定性。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 创建测试目录

我们首先为 CI/CD 相关的测试创建专属的目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p tests/cicd
touch tests/cicd/__init__.py
~~~~~

#### Acts 2: 创建 CI/CD 任务的测试文件

现在，我们将创建测试文件并填充内容。这些测试将使用 `pytest` 和 `unittest.mock.AsyncMock` 来模拟异步的 `cs.shell` 调用。

~~~~~act
write_file
tests/cicd/test_tasks.py
~~~~~
~~~~~python
import pytest
from unittest.mock import AsyncMock

# Since tasks are in a sibling directory, we might need to adjust path for local runs
# In a proper pytest setup, the root is usually added to PYTHONPATH, so this should work.
from cicd.tasks import (
    detect_changed_packages,
    lint_package,
    test_package,
    build_package,
)

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio


async def test_detect_changed_packages_with_changes(monkeypatch):
    """
    Verify that detect_changed_packages correctly parses git diff output.
    """
    mock_shell = AsyncMock()
    # Simulate git diff output for changes in two packages
    mock_shell.return_value = (
        "packages/cascade-sdk/src/cascade/__init__.py\n"
        "packages/cascade-engine/src/cascade/runtime/engine.py\n"
        "packages/cascade-sdk/pyproject.toml\n"
        "README.md\n"
    )
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    result = await detect_changed_packages()

    # Assert that the correct command was called
    mock_shell.assert_awaited_once_with("git diff --name-only origin/main...HEAD")
    
    # Assert that the output was parsed correctly and sorted
    assert result == ["cascade-engine", "cascade-sdk"]


async def test_detect_changed_packages_with_no_package_changes(monkeypatch):
    """
    Verify that detect_changed_packages returns an empty list if no packages changed.
    """
    mock_shell = AsyncMock()
    # Simulate git diff output with only top-level file changes
    mock_shell.return_value = "README.md\n.gitignore\n"
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    result = await detect_changed_packages()

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
            test_package,
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
    with the correctly formatted command.
    """
    mock_shell = AsyncMock()
    # The return value doesn't matter much here, we just need it to be awaitable
    mock_shell.return_value = "OK"
    monkeypatch.setattr("cicd.tasks.cs.shell", mock_shell)

    await task_func(package_name)

    # The key assertion: verify the correct command was executed
    mock_shell.assert_awaited_once_with(expected_command)
~~~~~
