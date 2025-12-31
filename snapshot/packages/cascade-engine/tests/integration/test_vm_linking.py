import pytest
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
import cascade as cs

@pytest.mark.asyncio
async def test_vm_strategy_performs_linking_and_execution():
    """
    端到端集成测试：
    1. 定义任务
    2. Engine (use_vm=True) 调用 Frontend 编译 -> 得到 Symbol Table
    3. Engine 调用 Backend 编译 -> 得到带 Hash 的 Blueprint (func=None)
    4. Engine 执行 Link 过程 -> 填充 Blueprint 的 func
    5. VM 执行成功
    
    RED 阶段预期：
    由于 Link 逻辑未实现，VM 尝试执行 func=None 的指令，抛出 TypeError。
    """
    @cs.task
    def echo(x):
        return x

    workflow = echo("hello_world")
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )
    
    # 使用 VM 执行
    try:
        result = await engine.run(workflow, use_vm=True)
    except TypeError as e:
        if "'NoneType' object is not callable" in str(e):
            # 这是我们预期的失败，证明 Link 没发生
            pytest.fail("VM crashed because function was not linked (func is None)")
        raise e
    except AttributeError as e:
        # 可能是 CompilationResult 还没实现导致的属性错误
        pytest.fail(f"Execution failed likely due to missing linking infrastructure: {e}")
    
    assert result == "hello_world"