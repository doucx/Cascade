from cascade.connectors.local import LocalBusConnector
# Re-export ControllerTestApp from the official SDK testing module
from cascade.testing import ControllerTestApp

# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally. 
InProcessConnector = LocalBusConnector

# ControllerTestApp is now imported from cascade.testing
__all__ = ["InProcessConnector", "ControllerTestApp"]