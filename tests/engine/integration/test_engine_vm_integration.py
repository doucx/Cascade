import pytest
from unittest.mock import MagicMock, patch
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.spec.blueprint import TailCall
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus


# --- Helper ---
@cs.task
def vm_task(x: int):
    return x + 1


@pytest.mark.asyncio
async def test_engine_dispatches_to_vm():
    """
    Verifies that Engine.run(..., use_vm=True) compiles and runs the task via VM.
    """
    # Setup Engine
    bus = MessageBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Target task
    target = vm_task(x=10)

    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.strategies.BlueprintBuilder") as MockBuilder, patch(
        "cascade.runtime.strategies.VirtualMachine"
    ) as MockVM:
        mock_builder_instance = MockBuilder.return_value
        mock_vm_instance = MockVM.return_value

        # Mock build result
        mock_bp = MagicMock()
        mock_builder_instance.build.return_value = mock_bp

        # Mock execute result
        mock_vm_instance.execute = MagicMock(return_value=11)

        # async mock is tricky, let's use a real async function or specific mock config
        # Simpler: just ensure the call happens. The execute needs to be awaitable.
        async def async_return(*args, **kwargs):
            return 11

        mock_vm_instance.execute.side_effect = async_return

        # Run with VM flag
        result = await engine.run(target, use_vm=True)

        # Assertions
        assert result == 11

        # Verify Builder was called with target in template mode
        mock_builder_instance.build.assert_called_once_with(target, template=True)

        # Verify VM was executed with the blueprint and initial kwargs
        # Note: The engine should extract initial kwargs from the target
        mock_vm_instance.execute.assert_called_once()
        call_args = mock_vm_instance.execute.call_args
        assert call_args[0][0] == mock_bp  # First arg is blueprint
        assert call_args[1]["initial_kwargs"] == {"x": 10}


@pytest.mark.asyncio
async def test_engine_vm_recursive_execution():
    """
    Integration test with a real recursive task (no mocks), verifying TCO.
    """

    # A real recursive task
    @cs.task
    def countdown(n: int):
        if n > 0:
            return TailCall(kwargs={"n": n - 1})
        return "Liftoff"

    bus = MessageBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    target = countdown(n=5)

    # Run with VM
    result = await engine.run(target, use_vm=True)

    assert result == "Liftoff"
