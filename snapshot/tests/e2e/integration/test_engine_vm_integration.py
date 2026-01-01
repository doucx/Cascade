import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.spec.blueprint import TailCall, Blueprint
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
    Verifies that Engine.run(..., use_vm=True) correctly dispatches to the
    new compiler pipeline (Backend) and VirtualMachine.
    """
    # Setup Engine
    bus = MessageBus()
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=bus)

    # Target task
    target = vm_task(x=10)

    # We patch Backend and VirtualMachine where they are imported by VMExecutionStrategy.
    with patch("cascade.runtime.strategies.vm.Backend") as MockBackend, patch(
        "cascade.runtime.strategies.vm.VirtualMachine"
    ) as MockVM:
        # 1. Setup mocks
        mock_bp = MagicMock(spec=Blueprint)
        MockBackend.compile.return_value = mock_bp

        mock_vm_instance = MockVM.return_value
        # The execute method is async, so we use AsyncMock for proper awaiting.
        mock_vm_instance.execute = AsyncMock(return_value=11)

        # 2. Run with VM flag
        result = await engine.run(target, use_vm=True)

        # 3. Assertions
        assert result == 11

        # Verify Backend.compile was called (it's a static method, so called on the class)
        MockBackend.compile.assert_called_once()

        # Verify a VM instance was created
        MockVM.assert_called_once()

        # Verify VM.execute was called with the correct blueprint and initial state
        mock_vm_instance.execute.assert_awaited_once()
        call_args, call_kwargs = mock_vm_instance.execute.call_args

        assert call_args[0] == mock_bp  # First positional arg is the blueprint
        assert "symbol_table" in call_kwargs  # Symbol table is passed
        assert call_kwargs["initial_kwargs"] == {"x": 10}


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
    # NOTE: This test will fail until the old BlueprintBuilder and VM in cascade-graph/engine are removed
    # and the new VM supports TailCall. The old ones do, but the new one might not yet.
    # Let's check cascade.vm.machine.py... it does handle TailCall. So this should pass.
    result = await engine.run(target, use_vm=True)

    assert result == "Liftoff"
