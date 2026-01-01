# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-python) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # This stub allows static analysis tools to be lenient when they resolve
    # this specific __init__.py but fail to merge it with cascade-python's definition.
    # It prevents "Env is not a known attribute" errors in local examples.
    def __getattr__(name: str) -> Any: ...
