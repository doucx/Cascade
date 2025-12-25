This is an excellent find. The CI failure is subtle and points to a problem with how our tools interact in a monorepo environment, especially after our refactoring.

错误分析

The key error is `coverage.exceptions.DataError: Couldn't use data file ... no such table: other_db.file`. This error originates from `pytest-cov`, the coverage plugin.

1.  **Root Cause**: Our CI workflow (`pr_check_workflow`) identifies all changed packages and then uses `.map()` to generate a separate `pytest` command for each one (e.g., `pytest packages/cascade-application`, `pytest packages/cascade-sdk`, etc.).
2.  **Concurrency Issue**: Each of these `pytest` commands is a separate process. Since `pytest-cov` is enabled globally (`--cov=cascade`), each process tries to write to the *same* `.coverage` database file in the project root.
3.  **File Corruption**: When multiple processes write to the same SQLite database file without proper coordination (which `pytest-cov` doesn't do by default), the file becomes corrupted. The error `no such table: other_db.file` indicates that one `pytest` process is trying to read or combine data from a table that another process hasn't created yet or has left in an inconsistent state. The crash happens when `pytest-cov` tries to combine the results at the end of a test run.

解决方案

The correct approach is not to run one `pytest` process per package, but to run a **single `pytest` process** that targets all changed packages simultaneously. `pytest` is designed to handle multiple directory paths as input. This will ensure that a single, coordinated `pytest-cov` instance manages the `.coverage` file, completely avoiding the race condition and file corruption.

I will create a plan to modify our CI workflow to generate and execute a single, aggregated test command.

## [WIP] fix(ci): Aggregate test commands to prevent coverage file corruption

### 错误分析
The CI build is failing with a `coverage.exceptions.DataError` because the workflow executes multiple `pytest --cov` commands in sequence for each changed package. Each of these processes attempts to write to the same `.coverage` SQLite database, leading to file corruption and a `sqlite3.OperationalError: no such table`.

### 用户需求
Fix the failing CI pipeline by resolving the `pytest-cov` file corruption issue.

### 评论
This is a classic monorepo CI challenge. The proposed solution is elegant because it aligns with `pytest`'s intended usage and solves the root cause—multiple processes interfering with a single state file—by consolidating them into a single, managed process.

### 目标
1.  Create a new task in `cicd/tasks.py` named `get_aggregated_test_command` that accepts a list of package names and generates a single `pytest` command string targeting all of them.
2.  Update `cicd/workflows.py` to use this new aggregated command task in both `pr_check_workflow` and `release_workflow`, replacing the `.map()` pattern with a single command execution for all tests.
3.  Remove the now-redundant `get_test_command` task.

### 基本原理
Instead of generating and running one `shell` command per changed package, we will generate a single command string (e.g., `pytest packages/pkg-a packages/pkg-b`). This single `pytest` invocation will discover and run all necessary tests in one go. Consequently, only one `pytest-cov` instance will be active, ensuring that the `.coverage` file is created and managed correctly without any race conditions or corruption.

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/state #scope/dx #ai/instruct

---
### Script

#### Acts 1: Update CI tasks to create a single test command

First, we'll modify `cicd/tasks.py` to replace the per-package test command generator with a new one that aggregates all package paths into a single command.

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
    return f"ruff check packages/{package_name}"


@cs.task
def get_aggregated_test_command(package_names: List[str]) -> str:
    """
    Generates a single pytest command to run tests for multiple packages.
    """
    if not package_names:
        return "echo 'No tests to run.'"
    paths = " ".join([f"packages/{name}" for name in package_names])
    return f"pytest {paths}"


@cs.task
def get_build_command(package_name: str) -> str:
    """
    Generates the shell command to build the package.
    """
    return f"hatch build packages/{package_name}"


@cs.task
def get_publish_command() -> str:
    """
    Generates the shell command to publish packages.
    """
    # Using 'twine upload' which expects credentials in env vars.
    return "TWINE_USERNAME=__token__ TWINE_PASSWORD=$PYPI_TOKEN twine upload 'dist/*'"
~~~~~

#### Acts 2: Update CI workflows to use the aggregated test command

Now, we'll update `cicd/workflows.py` to call our new task, ensuring only a single `pytest` command is executed for the entire test suite.

~~~~~act
write_file
cicd/workflows.py
~~~~~
~~~~~python
import os
import cascade as cs
from typing import List
from .tasks import (
    parse_git_diff,
    get_lint_command,
    get_aggregated_test_command,
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
    "cascade-application",
]


@cs.task
def _ci_success_marker(results: List[str]):
    """A dummy task to act as a final success node in the graph."""
    print("CI checks completed successfully.")
    print("Results:", results)
    return "CI_SUCCESS"


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

    # Step 4: Generate commands
    lint_commands = get_lint_command.map(package_name=changed_packages)
    # Generate one single test command for all changed packages
    test_command = get_aggregated_test_command(changed_packages)

    # Step 5: Execute commands
    lint_results = cs.shell.map(command=lint_commands)
    # Execute the single test command
    test_results = cs.shell(command=test_command)

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
    # Generate one single test command for all packages
    test_cmd = get_aggregated_test_command(ALL_PACKAGES)
    build_cmds = get_build_command.map(package_name=ALL_PACKAGES)
    publish_cmd = get_publish_command()

    # 2. Execute with dependencies
    lint_all = cs.shell.map(command=lint_cmds)

    # Execute the single test command
    test_all = cs.shell(command=test_cmd).after(lint_all)

    build_all = cs.shell.map(command=build_cmds).after(test_all)

    # publish_cmd is a LazyResult[str], passed to cs.shell
    publish_result = cs.shell(command=publish_cmd).after(build_all)

    return publish_result
~~~~~
