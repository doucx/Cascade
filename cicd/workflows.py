import cascade as cs
from typing import List
import cascade as cs
from .tasks import (
    parse_git_diff,
    lint_package,
    run_package_tests,
    build_package,
    publish_packages,
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

def pr_check_workflow() -> cs.LazyResult:
    """
    Workflow for Pull Requests and pushes to main.
    Only lints and tests the packages that have changed.
    """
    # Step 1: Declare the action to get git diff output. This returns a LazyResult[str].
    git_diff_output = cs.shell("git diff --name-only origin/main...HEAD")
    
    # Step 2: Declare the action to parse the output.
    # We pass the LazyResult from step 1 directly as an argument.
    # The Cascade engine will resolve it before executing parse_git_diff.
    changed_packages = parse_git_diff(git_diff_output)

    # Step 3: Use the result of the parsing to dynamically build the rest of the graph.
    lint_results = lint_package.map(package_name=changed_packages)
    test_results = run_package_tests.map(package_name=changed_packages)

    # Enforce order: tests run only after linting passes for all packages
    test_results.after(lint_results)

    # The final result of the workflow depends on the test results
    return _ci_success_marker(test_results)


def release_workflow() -> cs.LazyResult:
    """
    Workflow for releases (triggered by a tag).
    Lints, tests, and builds ALL packages, then publishes them.
    """
    # Lint all packages in parallel
    lint_all = lint_package.map(package_name=ALL_PACKAGES)

    # Test all packages after all linting is done
    test_all = run_package_tests.map(package_name=ALL_PACKAGES).after(lint_all)

    # Build all packages after all testing is done
    build_all = build_package.map(package_name=ALL_PACKAGES).after(test_all)

    # Publish after all builds are complete
    publish_result = publish_packages().after(build_all)
    
    return publish_result