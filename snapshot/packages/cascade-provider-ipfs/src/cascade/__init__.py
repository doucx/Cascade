# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
