## [WIP] feat(engine): 集成新编译器管线 (GREEN)

### 摘要头
## [WIP] feat(engine): 集成新编译器管线 (GREEN)

### 用户需求
修改 `cascade-engine`，使其 `VMExecutionStrategy` 切换使用新的 `cascade-compiler` 包。这将使集成测试 `test_engine_activates_new_compiler_pipeline` 通过。

### 评论
我们将在 `cascade/runtime/strategies/vm.py` 中进行“心脏移植”。我们将移除对旧版 `cascade.graph.compiler` 和 `cascade.runtime.vm` 的引用，代之以 `cascade.compiler` 中的 `Frontend`, `Optimizer`, `Backend`, 和 `VirtualMachine`。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`。
2.  在 `VMExecutionStrategy.execute` 中实现 `Frontend -> Optimizer -> Backend -> VM` 的完整调用链。
3.  确保 `packages/cascade-engine/tests/integration/test_compiler_integration.py` 测试通过。

### 基本原理
新的执行流程如下：
1.  **Frontend**: `LazyResult` -> `GraphIR`
2.  **Optimizer**: `GraphIR` -> `ExecutionPlan`
3.  **Backend**: `(GraphIR, ExecutionPlan)` -> `Blueprint`
4.  **VM**: `Blueprint` -> Result

这种管道式设计清晰地分离了关注点，并且每一阶段的数据契约（IR）都是显式定义的。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/integration #scope/core #ai/instruct #task/domain/refactor #task/object/engine-integration #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 重写 VMExecutionStrategy

我们将替换整个文件的内容，以确保没有任何旧依赖残留。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict

from cascade.spec.protocols import StateBackend
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager

# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.compiler.vm import VirtualMachine


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        graph_ir = Frontend.compile(target)

        # 2. Optimizer: Schedule GraphIR to ExecutionPlan
        execution_plan = Optimizer.optimize(graph_ir)

        # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
        blueprint = Backend.compile(graph_ir, execution_plan)

        # 4. Runtime: Execute Blueprint on VM
        # Note: The new VM doesn't yet support ResourceManager/ConstraintManager injection
        # directly in the same way. For Phase 5 initial integration, we instantiate the
        # pure VM. Future tasks will reintegrate resource management.
        vm = VirtualMachine()
        
        # Prepare initial arguments
        # The new VM expects 'initial_kwargs' mapping directly to registers if needed,
        # or it relies on the blueprint's structure.
        # For now, we assume the Blueprint structure handles defaults, but we need to pass
        # the runtime parameters if any.
        
        # Extract args/kwargs from target LazyResult for the root call
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)
~~~~~

#### Acts 2: 更新 Stitcher 文档

更新对应的 `.stitcher.yaml` 文件以反映新的实现逻辑。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.stitcher.yaml
~~~~~
~~~~~yaml
"VMExecutionStrategy": |-
  Executes tasks using the new compiler pipeline:
  Frontend -> Optimizer -> Backend -> VirtualMachine.
  This strategy decouples execution from the graph building process.
~~~~~

#### Acts 3: 更新测试 (GREEN)

我们需要稍微调整测试。之前在 RED 阶段，我们仅仅是断言 `mock_frontend_compile` 被调用。现在代码已经集成，我们可以运行测试了。
此外，我们需要在 `test_compiler_integration.py` 中移除 `try-except` 块，因为我们现在期望它能够无错误地运行（虽然它跑的是一个 mock 流程，但调用链是通的）。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_compiler_integration.py
~~~~~
~~~~~python
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
    with patch("cascade.compiler.frontend.Frontend.compile") as mock_front, \
         patch("cascade.compiler.optimizer.Optimizer.optimize") as mock_opt, \
         patch("cascade.compiler.backend.Backend.compile") as mock_back, \
         patch("cascade.compiler.vm.VirtualMachine.execute") as mock_vm_exec:

        # Setup Mocks
        mock_ir = MagicMock(spec=GraphIR)
        mock_front.return_value = mock_ir
        
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
~~~~~
