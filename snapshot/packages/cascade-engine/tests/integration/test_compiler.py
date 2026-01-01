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

    # 3. Patch the entire pipeline to verify wiring without running real logic
    # We want to ensure data flows: Frontend -> Optimizer -> Backend -> VM
    with patch("cascade.compiler.frontend.Frontend.compile") as mock_front, patch(
        "cascade.compiler.optimizer.Optimizer.optimize"
    ) as mock_opt, patch(
        "cascade.compiler.backend.Backend.compile"
    ) as mock_back, patch("cascade.vm.VirtualMachine.execute") as mock_vm_exec:
        # Setup Mocks
        mock_ir = MagicMock(spec=GraphIR)
        # Mock CompilationResult
        mock_comp_result = MagicMock()
        mock_comp_result.ir = mock_ir
        mock_comp_result.symbol_table = {}

        mock_front.return_value = mock_comp_result

        mock_plan = [["node_1"]]
        mock_opt.return_value = mock_plan

        mock_bp = MagicMock()
        mock_back.return_value = mock_bp

        mock_vm_exec.return_value = 11

        # 4. Act
        result = await engine.run(workflow, use_vm=True)

        # 5. Assert
        assert result == 11

        mock_front.assert_called_once_with(workflow)
        mock_opt.assert_called_once_with(mock_ir)
        mock_back.assert_called_once_with(mock_ir, mock_plan)
        mock_vm_exec.assert_called_once()
        # Verify VM received the blueprint
        assert mock_vm_exec.call_args[0][0] == mock_bp
