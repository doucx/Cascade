class CompilerError(Exception):
    """Base class for compiler-related errors."""
    pass

class CycleDetectedError(CompilerError):
    """Raised when a cycle is detected in the dependency graph."""
    pass