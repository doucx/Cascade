import pytest
from typing import Callable, Type
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol


def pytest_addoption(parser):
    """Adds a command-line option to select the reactor backend."""
    parser.addoption(
        "--reactor-backend",
        action="store",
        default="python",
        help="Select reactor backend to test: python or rust",
    )


@pytest.fixture(scope="session")
def reactor_backend_factory(
    request,
) -> Type[ReactorProtocol]:
    """
    A session-scoped fixture that provides the Reactor class
    based on the --reactor-backend command-line option.
    """
    backend = request.config.getoption("--reactor-backend")

    if backend == "python":
        # Return the Python implementation
        return Reactor
    elif backend == "rust":
        # Import the high-performance Rust implementation
        from cascade_vm_rs import RustReactor
        return RustReactor
    else:
        pytest.fail(
            f"Invalid reactor backend specified: '{backend}'. "
            "Choose from 'python' or 'rust'."
        )
