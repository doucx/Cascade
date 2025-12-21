## [WIP] feat(engine): Integrate VM execution path into Engine

### 摘要头
`# [WIP] feat(engine): Integrate VM execution path into Engine`

### 用户需求
1.  将 AOT/VM 执行路径集成到 `Engine.run` 中。
2.  当用户显式请求（例如通过参数 `use_vm=True`）时，`Engine` 应使用 `BlueprintBuilder` 编译任务，并使用 `VirtualMachine` 执行，而不是使用传统的图求解器。

### 评论
这是连接新旧世界的桥梁。一旦完成，我们就可以在不破坏现有 API 的情况下，为特定的高性能任务（如 Agent 循环）启用 VM 模式。这为最终的无缝切换奠定了基础。

### 目标
1.  编写 `test_engine_dispatches_to_vm` 测试用例。
2.  修改 `Engine.run` 方法，接受 `use_vm` 参数（或类似的触发机制）。
3.  在 `Engine` 内部实例化 `BlueprintBuilder` 和 `VirtualMachine` 并委托执行。

### 基本原理
为了最小化对现有逻辑的侵入，我们将在 `Engine.run` 的最外层添加一个分支判断。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 创建引擎集成测试 (`test_engine_integration.py`)
我们需要验证 `Engine` 是否正确地将执行委托给了 VM。

~~~~~act
write_file
tests/cascade-runtime/integration/test_engine_vm_integration.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock, patch
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.runtime.blueprint import TailCall
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
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    
    # Target task
    target = vm_task(x=10)
    
    # Mock BlueprintBuilder and VirtualMachine to verify interaction
    with patch("cascade.runtime.engine.BlueprintBuilder") as MockBuilder, \
         patch("cascade.runtime.engine.VirtualMachine") as MockVM:
        
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
        
        # Verify Builder was called with target
        mock_builder_instance.build.assert_called_once_with(target)
        
        # Verify VM was executed with the blueprint and initial kwargs
        # Note: The engine should extract initial kwargs from the target
        mock_vm_instance.execute.assert_called_once()
        call_args = mock_vm_instance.execute.call_args
        assert call_args[0][0] == mock_bp # First arg is blueprint
        assert call_args[1]['initial_kwargs'] == {'x': 10}

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
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    
    target = countdown(n=5)
    
    # Run with VM
    result = await engine.run(target, use_vm=True)
    
    assert result == "Liftoff"
~~~~~

#### Acts 2: 修改 `Engine` 以支持 VM 路径 (`engine.py`)
我们需要导入 `BlueprintBuilder` 和 `VirtualMachine`，并在 `run` 方法中添加逻辑分支。
同时，我们需要从 `target` 中提取初始参数（`args`/`kwargs`）传递给 VM。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """
~~~~~
~~~~~python
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine


class Engine:
    """
    Orchestrates the entire workflow execution.
    """
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def override_resource_provider(self, name: str, new_provider: Any):
        # When overriding, we might lose metadata if a raw function is passed,
        # but that's acceptable for testing overrides.
        self._resource_providers[name] = new_provider

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
~~~~~
~~~~~python
    def override_resource_provider(self, name: str, new_provider: Any):
        # When overriding, we might lose metadata if a raw function is passed,
        # but that's acceptable for testing overrides.
        self._resource_providers[name] = new_provider

    async def run(
        self, 
        target: Any, 
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = False
    ) -> Any:
        # VM Fast Path
        if use_vm:
            return await self._run_vm(target)

        run_id = str(uuid4())
        start_time = time.time()
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
~~~~~
~~~~~python
            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

    async def _run_vm(self, target: Any) -> Any:
        """
        Executes the target using the AOT Blueprint/VM path.
        """
        # 1. Compile
        builder = BlueprintBuilder()
        blueprint = builder.build(target)

        # 2. Extract Initial Arguments
        # The BlueprintBuilder treats the root LazyResult's args/kwargs as the
        # inputs for the blueprint.
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine()
        # TODO: Inject resources and specialized executors into VM if needed.
        # For now, VM uses direct function calls.
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
~~~~~

### 下一步建议
运行 `tests/cascade-runtime/integration/test_engine_vm_integration.py` 验证集成是否成功。
如果成功，我们将进入最后一个任务：**使用 `kuramoto.py` 和 `run_fireflies.py` 进行验证**，这将是一个激动人心的时刻！
