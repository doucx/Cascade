完全明白。你的审查非常敏锐。

正如你所指出的，我之前的修复是不完整的。我虽然重构了 `detect_changed_packages`，但遗漏了 `lint_package` 等其他任务中同样的根本性错误：**在 Task 内部 `await` 一个 `LazyResult`**。

在 Cascade 的运行时模型中（参考 `engine.py` 的 TCO 逻辑），如果一个任务想要触发另一个任务（例如 `shell`），它不应该去 `await` 它，而应该**直接返回该 `LazyResult` 对象**。Cascade 引擎会识别出返回值是一个新的任务描述，并无缝地通过尾调用优化（Tail Call Optimization）切换去执行那个新任务。

我将立即修正所有任务定义以及文档中的示例。

## [WIP] fix(cicd): correct task implementation to use Tail Call Optimization

### 错误分析
在 `cicd/tasks.py` 和文档示例中，多个任务（如 `lint_package`）被定义为 `async` 并尝试 `await cs.shell(...)`。
1.  `cs.shell(...)` 返回的是一个 `LazyResult`（任务配方），而不是协程，因此不可 `await`。
2.  正确的模式是利用 Cascade 引擎的 TCO 机制：任务应该是一个同步函数，它构建并**返回** `cs.shell(...)` 的结果。引擎会自动接管并执行返回的新任务。

### 用户需求
彻底修复 `cicd` 目录下的所有 `TypeError`，确保没有遗留的 `await LazyResult` 模式，并更新文档以反映正确的用法。

### 评论
这次修复将把我们的 CI/CD 代码库从“错误的异步调用”纠正为“正确的声明式组合”。通过移除 `async/await` 并直接返回 `LazyResult`，我们不仅修复了崩溃问题，还正确利用了 Cascade 的核心特性——动态任务展开（Dynamic Task Expansion）和尾调用执行。

### 目标
1.  **重构 `cicd/tasks.py`**: 将 `lint_package`, `run_package_tests`, `build_package` 和 `publish_packages` 修改为同步函数，并直接返回 `cs.shell` 的结果。
2.  **修正 `cicd/README.md`**: 更新文档中的“扩展指南”示例，展示正确的任务编写方式。
3.  **清理无效逻辑**: 移除 `publish_packages` 中对 `cs.Env` 返回值的无效布尔检查（`if not pypi_token` 永远为真，因为它是对象）。

### 基本原理
-   **TCO 模式**: `def task_a(): return cs.shell(...)` 是 Cascade 中组合原子能力的标准方式。
-   **返回值透传**: 修改后的任务将不再返回自定义的字符串（如 `"LINT_OK"`），而是直接返回 `cs.shell` 的输出（stdout），这更符合 Unix 哲学的管道思维。

### 标签
#intent/fix #intent/document #flow/ready #priority/high #comp/build #comp/docs #scope/core #ai/instruct #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `cicd/tasks.py` 中的所有任务

我们将重写这些任务，移除 `async/await`，改用直接返回 `LazyResult` 的模式。

~~~~~act
write_file
cicd/tasks.py
~~~~~
~~~~~python
import cascade as cs
import re
from typing import List

@cs.task
def parse_git_diff(git_diff_output: str) -> List[str]:
    """
    Parses the output of 'git diff --name-only' and extracts changed package names.
    This is a pure logic task with no I/O.
    """
    changed_packages = set()
    package_pattern = re.compile(r"^packages/([^/]+)/.*")

    for line in git_diff_output.splitlines():
        match = package_pattern.match(line)
        if match:
            changed_packages.add(match.group(1))
    
    if not changed_packages:
        print("No package changes detected.")
        return []

    sorted_packages = sorted(list(changed_packages))
    print(f"Detected changed packages: {sorted_packages}")
    return sorted_packages

@cs.task
def lint_package(package_name: str) -> cs.LazyResult:
    """
    Returns a shell task to run ruff on the package.
    The engine will execute the returned LazyResult via TCO.
    """
    print(f"Scheduling lint for {package_name}...")
    return cs.shell(f"uv run -- ruff check packages/{package_name}")

@cs.task
def run_package_tests(package_name: str) -> cs.LazyResult:
    """
    Returns a shell task to run pytest on the package.
    """
    print(f"Scheduling tests for {package_name}...")
    return cs.shell(f"uv run -- pytest packages/{package_name}")

@cs.task
def build_package(package_name: str) -> cs.LazyResult:
    """
    Returns a shell task to build the package.
    """
    print(f"Scheduling build for {package_name}...")
    return cs.shell(f"uv run -- hatch build packages/{package_name}")

@cs.task
def publish_packages() -> cs.LazyResult:
    """
    Returns a shell task to publish packages.
    Note: We rely on the environment (PYPI_TOKEN) being correctly injected 
    into the shell process by the CI runner or cs.shell.
    """
    print("Scheduling publish task...")
    # Using 'twine upload' which expects credentials in env vars 
    # (TWINE_USERNAME, TWINE_PASSWORD) or ~/.pypirc.
    # In our GHA, we map PYPI_TOKEN. We need to ensure twine sees it.
    # The simplest way in a shell command is setting it inline or assuming GHA env is passed.
    # Cascade's LocalExecutor passes os.environ, so GHA env vars work.
    # We use username '__token__' for PyPI token auth.
    return cs.shell("TWINE_USERNAME=__token__ TWINE_PASSWORD=$PYPI_TOKEN uv run -- twine upload 'dist/*'")
~~~~~

#### Acts 2: 修正文档中的错误示例

同步更新 README，以免误导未来的开发者。

~~~~~act
patch_file
cicd/README.md
~~~~~
~~~~~markdown
1.  **添加任务**: 在 `cicd/tasks.py` 中创建一个新的 Cascade 任务。
    ```python
    @cs.task
    async def format_package(package_name: str) -> str:
        await cs.shell(f"uv run -- blue packages/{package_name}")
        return f"FORMAT_OK_{package_name}"
    ```
2.  **整合到工作流**: 在 `cicd/workflows.py` 中，将新任务添加到 `pr_check_workflow` 的依赖图中。
~~~~~
~~~~~markdown
1.  **添加任务**: 在 `cicd/tasks.py` 中创建一个新的 Cascade 任务。
    ```python
    @cs.task
    def format_package(package_name: str) -> cs.LazyResult:
        # 直接返回 cs.shell 创建的 LazyResult，引擎会自动执行它 (TCO)
        return cs.shell(f"uv run -- blue packages/{package_name}")
    ```
2.  **整合到工作流**: 在 `cicd/workflows.py` 中，将新任务添加到 `pr_check_workflow` 的依赖图中。
~~~~~

#### Acts 3: 更新测试以匹配 TCO 模式

由于任务实现变了（不再是 `async`，且返回 `LazyResult`），我们需要微调测试代码。现在的测试应该验证任务函数是否返回了正确的 `LazyResult` 对象，而不是模拟 `cs.shell` 的执行。

~~~~~act
write_file
tests/cicd/test_tasks.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import cascade as cs

from cicd.tasks import (
    parse_git_diff,
    lint_package,
    run_package_tests,
    build_package,
)

# parse_git_diff is still a logic task, so we test it normally (but it's synchronous now)
def test_parse_git_diff_with_changes():
    diff_output = (
        "packages/cascade-sdk/src/cascade/__init__.py\n"
        "packages/cascade-engine/src/cascade/runtime/engine.py\n"
        "packages/cascade-sdk/pyproject.toml\n"
        "README.md\n"
    )
    # Call the underlying function directly
    result = parse_git_diff.func(diff_output)
    assert result == ["cascade-engine", "cascade-sdk"]

def test_parse_git_diff_no_changes():
    diff_output = "README.md\n"
    result = parse_git_diff.func(diff_output)
    assert result == []

# For the wrapper tasks, we now check if they return a LazyResult 
# with the expected shell command.
@pytest.mark.parametrize(
    "task_func, package_name, expected_snippet",
    [
        (lint_package, "cascade-sdk", "ruff check packages/cascade-sdk"),
        (run_package_tests, "cascade-engine", "pytest packages/cascade-engine"),
        (build_package, "cascade-graph", "hatch build packages/cascade-graph"),
    ],
)
def test_package_task_generation(task_func, package_name, expected_snippet):
    # Call the underlying function
    lazy_result = task_func.func(package_name)
    
    # Assert it returns a LazyResult
    assert isinstance(lazy_result, cs.LazyResult)
    # Assert the task is 'shell'
    assert lazy_result.task.name == "shell"
    # Assert the command (first arg) contains our expected string
    command = lazy_result.args[0]
    assert expected_snippet in command
~~~~~
