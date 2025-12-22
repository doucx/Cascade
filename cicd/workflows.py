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