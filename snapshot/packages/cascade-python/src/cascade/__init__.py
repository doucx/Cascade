# This __init__.py makes 'cascade-python' a regular package that claims the 'cascade' namespace.
# The actual API definition has been moved to 'cascade-sdk' (src/cascade/__init__.py).
# This package now serves primarily as a distribution bundle.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)