# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)