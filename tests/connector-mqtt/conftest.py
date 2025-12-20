import sys
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def mock_aiomqtt_module(mocker):
    """
    Creates a completely isolated, fake 'aiomqtt' module and injects it into
    sys.modules.

    CRITICAL: This fixture also aggressively removes 'cascade.connectors.mqtt'
    from sys.modules to force a reload. This guarantees that the business logic
    imports our FAKE aiomqtt, even if the REAL one was loaded by a previous test.
    """
    # 1. Force reload of the target module
    # We must remove any existing loaded versions of our connector modules
    # so that they are forced to re-import 'aiomqtt' (which we are about to mock).
    modules_to_unload = [
        "cascade.connectors.mqtt",
        "cascade.connectors.mqtt.connector"
    ]
    for mod in modules_to_unload:
        if mod in sys.modules:
            del sys.modules[mod]

    # 2. Create the mock client INSTANCE
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # 3. Create the fake aiomqtt.Client CLASS
    # Note: We use a side_effect to return the instance, ensuring it behaves like a constructor
    mock_client_class = MagicMock(return_value=mock_client_instance)

    # 4. Create the fake aiomqtt.Will CLASS
    mock_will_class = MagicMock()

    # 5. Create the fake aiomqtt MODULE object
    mock_aiomqtt_module_obj = MagicMock()
    mock_aiomqtt_module_obj.Client = mock_client_class
    mock_aiomqtt_module_obj.Will = mock_will_class

    # 6. Patch sys.modules to replace/inject the real aiomqtt with our fake one
    mocker.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt_module_obj})

    yield {
        "instance": mock_client_instance,
        "Client": mock_client_class,
        "Will": mock_will_class,
    }