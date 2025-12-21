class CascadeRuntimeError(Exception):
    """Base class for runtime errors in Cascade."""

    pass


class DependencyMissingError(CascadeRuntimeError):
    """
    Raised when a task cannot execute because an upstream dependency result is missing.
    This usually happens if the upstream task was skipped or failed silently.
    """

    def __init__(self, task_id: str, arg_name: str, dependency_id: str):
        self.task_id = task_id
        self.arg_name = arg_name
        self.dependency_id = dependency_id
        super().__init__(
            f"Task '{task_id}' cannot execute: missing input for argument '{arg_name}'. "
            f"Dependency '{dependency_id}' did not produce a result (it may have been skipped)."
        )


class ResourceNotFoundError(CascadeRuntimeError):
    """Raised when a requested resource is not available in the context."""

    def __init__(self, resource_name: str, consumer_name: str = "unknown"):
        super().__init__(
            f"Resource '{resource_name}' required by '{consumer_name}' was not found. "
            "Ensure it is registered with the Engine or provided via system_resources."
        )
