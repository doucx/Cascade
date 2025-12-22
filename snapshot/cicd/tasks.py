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
async def lint_package(package_name: str) -> str:
    """Runs ruff linter on a specific package."""
    print(f"Linting {package_name}...")
    await cs.shell(f"uv run -- ruff check packages/{package_name}")
    return f"LINT_OK_{package_name}"

@cs.task
async def run_package_tests(package_name: str) -> str:
    """Runs pytest on a specific package."""
    print(f"Testing {package_name}...")
    await cs.shell(f"uv run -- pytest packages/{package_name}")
    return f"TEST_OK_{package_name}"

@cs.task
async def build_package(package_name: str) -> str:
    """Builds a specific package using hatch."""
    print(f"Building {package_name}...")
    # Hatch runs from the workspace root and can build specific packages
    await cs.shell(f"uv run -- hatch build packages/{package_name}")
    return f"BUILD_OK_{package_name}"

@cs.task
async def publish_packages() -> str:
    """Publishes all built packages to PyPI."""
    pypi_token = cs.Env("PYPI_TOKEN")
    if not pypi_token:
        raise ValueError("PYPI_TOKEN environment variable is not set.")
    
    print("Publishing all packages to PyPI...")
    # Twine will automatically find all packages in the top-level dist/ directory
    await cs.shell("uv run -- twine upload 'dist/*'")
    return "PUBLISH_OK"