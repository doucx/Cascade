# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass