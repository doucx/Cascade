You are absolutely right. My apologies. I refactored the task generation logic by removing `get_test_command` but completely forgot to update its corresponding test file. The `ImportError` is a direct result of my oversight.

I will now create a plan to fix this by updating the test file to match the new implementation.

## [WIP] fix(ci): Update tests to match refactored command generation logic

### 错误分析
During the previous refactoring, I removed the `get_test_command` function from `cicd/tasks.py` and replaced it with `get_aggregated_test_command`. However, I failed to update `cicd/tests/test_tasks.py`, which was still attempting to import and test the now-deleted function, leading to a test collection `ImportError`.

### 用户需求
Fix the `pytest` error in the `cicd` tests.

### 评论
This is a straightforward but necessary fix to synchronize the test code with the refactored source code. It completes the previous change by ensuring the new logic is properly tested.

### 目标
1.  Modify `cicd/tests/test_tasks.py` to stop importing `get_test_command`.
2.  Remove the test case for the obsolete `get_test_command` function.
3.  Add new test cases for the `get_aggregated_test_command` function to ensure its logic is correctly validated, including the edge case of an empty package list.

### 基本原理
We will use a `write_file` operation to replace the contents of `cicd/tests/test_tasks.py`. The new content will correctly import the new `get_aggregated_test_command` function and include parametrized tests that verify its behavior for multiple packages, a single package, and an empty list of packages.

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct

---
### Script

#### Acts 1: Synchronize CI task tests with source code

We will rewrite the test file to correctly test the new and existing CI tasks.

~~~~~act
write_file
cicd/tests/test_tasks.py
~~~~~
~~~~~python
import pytest

from cicd.tasks import (
    parse_git_diff,
    get_lint_command,
    get_aggregated_test_command,
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
        (get_build_command, "cascade-graph", "hatch build packages/cascade-graph"),
    ],
)
def test_single_package_command_generation(task_func, package_name, expected_snippet):
    # Call the underlying function directly
    # These are now pure functions returning strings, so they are trivial to test
    cmd_string = task_func.func(package_name)

    assert isinstance(cmd_string, str)
    assert expected_snippet in cmd_string


@pytest.mark.parametrize(
    "package_list, expected_command",
    [
        (
            ["cascade-engine", "cascade-sdk"],
            "pytest packages/cascade-engine packages/cascade-sdk",
        ),
        (["cascade-graph"], "pytest packages/cascade-graph"),
        ([], "echo 'No tests to run.'"),
    ],
)
def test_get_aggregated_test_command(package_list, expected_command):
    """Tests the aggregated test command generation."""
    cmd_string = get_aggregated_test_command.func(package_list)
    assert cmd_string == expected_command
~~~~~
