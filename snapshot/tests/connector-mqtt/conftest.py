import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def mock_aiomqtt_module(mocker):
    """
    Creates a completely isolated, fake 'aiomqtt' module and injects it into
    sys.modules for the duration of the tests in this directory.

    This is defined in conftest.py to ensure it runs BEFORE the test module
    is imported, thus patching the dependency before it's ever loaded.
    """
    # 1. Create the mock client INSTANCE that will be returned by the fake Client class
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance

    # 2. Create the fake aiomqtt.Client CLASS (a factory for the instance)
    mock_client_class = MagicMock(return_value=mock_client_instance)

    # 3. Create the fake aiomqtt.Will CLASS
    mock_will_class = MagicMock()

    # 4. Create the fake aiomqtt MODULE object
    mock_aiomqtt_module_obj = MagicMock()
    mock_aiomqtt_module_obj.Client = mock_client_class
    mock_aiomqtt_module_obj.Will = mock_will_class

    # 5. Patch sys.modules to replace the real aiomqtt with our fake one
    mocker.patch.dict("sys.modules", {"aiomqtt": mock_aiomqtt_module_obj})

    # Yield the components for tests to use, if they need to make assertions
    yield {
        "instance": mock_client_instance,
        "Client": mock_client_class,
        "Will": mock_will_class,
    }