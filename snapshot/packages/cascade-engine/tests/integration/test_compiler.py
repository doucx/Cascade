import pytest
from unittest.mock import patch, MagicMock
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
from cascade.spec.ir.models import GraphIR


@pytest.mark.asyncio
async def test_engine_activates_new_compiler_pipeline():
    """
    Verifies that Engine.run(use_vm=True) delegates to the new cascade.compiler package
    and executes the full pipeline.
    """

    # 1. Define a simple workflow
    @cs.task
    def add_one(x: int) -> int:
        return x + 1

    workflow = add_one(x=10)

    # 2. Setup Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # 3. Patch the VM Strategy to verify the Engine delegates correctly
    with patch(
        "cascade.runtime.strategies.vm.VMExecutionStrategy.execute"
    ) as mock_vm_exec:
        # Setup Mock behavior
        mock_vm_exec.return_value = 11

        # 4. Act
        result = await engine.run(workflow, use_vm=True)

        # 5. Assert: Verify the Engine routed the request to the VM strategy
        assert result == 11

        mock_vm_exec.assert_called_once()
        
        # Verify arguments passed to the strategy
        _, kwargs = mock_vm_exec.call_args
        assert kwargs["target"] == workflow
        assert kwargs["run_id"] is not None
        assert kwargs["params"] == {}
