import cascade as cs
from typing import List
from .tasks import (
    detect_changed_packages,
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
    changed = detect_changed_packages()

    # Dynamically create lint and test tasks for each changed package
    lint_results = lint_package.map(package_name=changed)
    test_results = run_package_tests.map(package_name=changed)

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