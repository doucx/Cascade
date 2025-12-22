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