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
