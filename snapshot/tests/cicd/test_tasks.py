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