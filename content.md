简要回答：
遵循“Cascade 编程模型”，我们将重构 CI/CD 代码，消除“任务返回任务 (TCO Anti-pattern)”的黑盒模式。

我们将 `cicd/tasks.py` 中的任务职责从“执行者”转变为“配方生成器 (Recipe Generators)”。这些任务将只返回纯命令字符串，而真正的 `cs.shell` 执行将在 `workflows.py` 中显式声明。这使得整个 CI/CD 执行图对静态分析（如 `visualize`）完全透明，并符合“声明式组合”的原则。

## [WIP] refactor(ci): align pipeline with cascade programming model

### 用户需求
重构 `cicd` 模块，使其符合 `Cascade Programming Model` 文档中定义的原则。具体来说，消除在 `@cs.task` 内部返回 `cs.shell` (LazyResult) 的反模式，转而采用“任务生成命令字符串，工作流负责执行命令”的透明模式。

### 评论
当前的实现虽然利用了 TCO (尾调用优化) 能够运行，但它创建了“黑盒”任务。静态分析器看到的只是 `lint_package`，而看不到内部真正发生的 `shell` 操作。重构后，`cs.visualize()` 将能清晰地展示 `generate_command` -> `shell` 的数据流，且逻辑与副作用分离，更易于测试。

### 目标
1.  修改 `cicd/tasks.py`：将所有执行 Shell 的任务重命名并修改为返回 `str` 的纯函数。
2.  修改 `cicd/workflows.py`：更新工作流逻辑，显式调用 `cs.shell.map` 或 `cs.shell` 来执行由上一步生成的命令。
3.  修改 `tests/cicd/test_tasks.py`：更新测试用例以验证生成的字符串，而非 LazyResult。

### 基本原理
**透明性原则 (Transparency)**：工作流图（Graph）应当是静态可分析的。通过将命令生成（逻辑）与命令执行（副作用）解耦，我们将隐式的运行时行为转化为了显式的图结构。这也是 Cascade 推荐的最佳实践。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #concept/workflow #scope/core #ai/instruct #task/domain/ops #task/object/ci-pipeline #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `tasks.py` 为纯逻辑生成器

我们将重命名任务以反映其新职责（例如 `lint_package` -> `get_lint_command`），并移除所有 `cs.shell` 调用，改为直接返回命令字符串。

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
def get_lint_command(package_name: str) -> str:
    """
    Generates the shell command to run ruff on the package.
    """
    return f"uv run -- ruff check packages/{package_name}"

@cs.task
def get_test_command(package_name: str) -> str:
    """
    Generates the shell command to run pytest on the package.
    """
    return f"uv run -- pytest packages/{package_name}"

@cs.task
def get_build_command(package_name: str) -> str:
    """
    Generates the shell command to build the package.
    """
    return f"uv run -- hatch build packages/{package_name}"

@cs.task
def get_publish_command() -> str:
    """
    Generates the shell command to publish packages.
    """
    # Using 'twine upload' which expects credentials in env vars.
    return "TWINE_USERNAME=__token__ TWINE_PASSWORD=$PYPI_TOKEN uv run -- twine upload 'dist/*'"
~~~~~

#### Acts 2: 更新 `workflows.py` 以显式组合 Shell 任务

现在我们在工作流层面进行组合。逻辑是：`[Generators]` -> `[Shell Executor]`。这使得 `shell` 节点在图中清晰可见。

~~~~~act
write_file
cicd/workflows.py
~~~~~
~~~~~python
import cascade as cs
from typing import List
from .tasks import (
    parse_git_diff,
    get_lint_command,
    get_test_command,
    get_build_command,
    get_publish_command,
)

# List of all packages in the monorepo for full runs.
ALL_PACKAGES = [
    "cascade-spec",
    "cascade-common",
    "cascade-graph",
    "cascade-engine",
    "cascade-sdk",
    "cascade-library",
    "cascade-connector-local",
    "cascade-connector-mqtt",
    "cascade-cli-controller",
    "cascade-cli-observer",
    "cascade-provider-ipfs",
]


@cs.task
def _ci_success_marker(results: List[str]):
    """A dummy task to act as a final success node in the graph."""
    print("CI checks completed successfully.")
    print("Results:", results)
    return "CI_SUCCESS"


import os

def pr_check_workflow() -> cs.LazyResult:
    """
    Workflow for Pull Requests and pushes to main.
    Only lints and tests the packages that have changed.
    """
    # Step 1: Determine the correct git diff command based on the CI environment.
    event_name = os.getenv("GITHUB_EVENT_NAME")
    
    if event_name == "pull_request":
        base_ref = os.getenv("GITHUB_BASE_REF", "main")
        diff_command = f"git diff --name-only origin/{base_ref}...HEAD"
        print(f"Running diff for Pull Request: {diff_command}")
    else: 
        diff_command = "git diff --name-only HEAD~1 HEAD"
        print(f"Running diff for Push/Local: {diff_command}")

    # Step 2: I/O - Get git diff
    git_diff_output = cs.shell(diff_command)
    
    # Step 3: Pure Logic - Parse output
    changed_packages = parse_git_diff(git_diff_output)

    # Step 4: Pure Logic - Generate commands (Recipe Generation)
    # These return LazyResult[List[str]]
    lint_commands = get_lint_command.map(package_name=changed_packages)
    test_commands = get_test_command.map(package_name=changed_packages)

    # Step 5: I/O - Execute commands (Explicit Execution)
    # The 'command' argument of cs.shell will be resolved from the upstream lists
    lint_results = cs.shell.map(command=lint_commands)
    test_results = cs.shell.map(command=test_commands)

    # Enforce order: tests run only after linting passes for all packages
    test_results.after(lint_results)

    # The final result of the workflow depends on the test results
    return _ci_success_marker(test_results)


def release_workflow() -> cs.LazyResult:
    """
    Workflow for releases (triggered by a tag).
    Lints, tests, and builds ALL packages, then publishes them.
    """
    # 1. Generate commands
    lint_cmds = get_lint_command.map(package_name=ALL_PACKAGES)
    test_cmds = get_test_command.map(package_name=ALL_PACKAGES)
    build_cmds = get_build_command.map(package_name=ALL_PACKAGES)
    publish_cmd = get_publish_command()

    # 2. Execute with dependencies
    lint_all = cs.shell.map(command=lint_cmds)
    
    test_all = cs.shell.map(command=test_cmds).after(lint_all)
    
    build_all = cs.shell.map(command=build_cmds).after(test_all)

    # publish_cmd is a LazyResult[str], passed to cs.shell
    publish_result = cs.shell(command=publish_cmd).after(build_all)

    return publish_result
~~~~~

#### Acts 3: 更新测试用例

测试用例现在变得更简单、更直接了。我们不再检查返回的是否是包含 `shell` 的 `LazyResult`，而是检查它是否返回了预期的字符串。

~~~~~act
write_file
tests/cicd/test_tasks.py
~~~~~
~~~~~python
import pytest
import cascade as cs

from cicd.tasks import (
    parse_git_diff,
    get_lint_command,
    get_test_command,
    get_build_command,
)

# parse_git_diff is still a logic task, so we test it normally
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

# Tests for the command generator tasks
@pytest.mark.parametrize(
    "task_func, package_name, expected_snippet",
    [
        (get_lint_command, "cascade-sdk", "ruff check packages/cascade-sdk"),
        (get_test_command, "cascade-engine", "pytest packages/cascade-engine"),
        (get_build_command, "cascade-graph", "hatch build packages/cascade-graph"),
    ],
)
def test_command_generation(task_func, package_name, expected_snippet):
    # Call the underlying function directly
    # These are now pure functions returning strings, so they are trivial to test
    cmd_string = task_func.func(package_name)
    
    assert isinstance(cmd_string, str)
    assert expected_snippet in cmd_string
~~~~~

### 下一步建议
运行本地测试 `pytest tests/cicd/` 以验证新的任务逻辑。如果通过，可以考虑为 `workflows.py` 添加结构测试（如指导原则中提到的 `test_pr_check_workflow_structure`），以静态验证图的正确性。
