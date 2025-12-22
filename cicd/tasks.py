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