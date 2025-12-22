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
