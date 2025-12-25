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