# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-engine) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .connector import SqliteConnector

__all__ = ["SqliteConnector"]