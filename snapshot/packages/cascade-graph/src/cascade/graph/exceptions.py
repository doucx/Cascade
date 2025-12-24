class CascadeGraphError(Exception):
    """Base class for errors in the cascade-graph package."""

    pass


class StaticGraphError(CascadeGraphError):
    """
    Raised when an anti-pattern that violates static graph principles
    is detected during the build process.
    """

    pass
