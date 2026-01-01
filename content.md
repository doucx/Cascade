好的，我已收到你的指示。问题明确，解决方案清晰。我将使用 `write_file` 指令来修正 `test_reactor_emits_result_to_sink` 函数，使其不再依赖 `event_loop` fixture。

## [WIP] fix(vm): 修复 `test_result_emission.py` 的 `event_loop` fixture 依赖

### 用户需求
根据提供的错误信息和修正方案，修改 `packages/cascade-vm/tests/reactor/test_result_emission.py` 文件中的 `test_reactor_emits_result_to_sink` 函数，移除对 `event_loop` fixture 的依赖。

### 评论
这个修复是必要的，因为测试环境可能未提供 `event_loop` fixture。通过使用 `asyncio.get_running_loop().create_future()`，我们能直接获取当前正在运行的事件循环并创建 future，从而使测试在更广泛的 `pytest-asyncio` 配置下（或不依赖特定 fixture 的情况下）运行。这增加了测试的健壮性和可移植性。

### 目标
1.  从 `test_reactor_emits_result_to_sink` 函数签名中移除 `event_loop` 参数。
2.  将 `event_loop.create_future()` 的调用修改为 `asyncio.get_running_loop().create_future()`。

### 基本原理
`pytest-asyncio` 插件在执行 `async` 测试函数时，会自动设置一个事件循环。因此，直接从 `asyncio.get_running_loop()` 获取循环是可靠且标准的做法，避免了对 `event_loop` fixture 的显式依赖。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #scope/dx
#ai/instruct
#task/domain/testing #task/object/asyncio-test-fix #task/action/test-adaptation
#task/state/continue

---

### Script

#### Acts 1: 修正 `test_result_emission.py` 文件

我们将修改 `test_reactor_emits_result_to_sink` 函数的签名和内部对 `event_loop` 的引用。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_result_emission.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode
from cascade.vm.reactor import Reactor, TokenGenerated

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink():
    """
    Verifies that an EmitterNode correctly pushes data to an external sink,
    and that the Reactor can be gracefully stopped by an external controller
    after the emission occurs.
    
    This test validates the decoupled lifecycle model.
    """
    # 1. Setup simplified topology: D_in -> Emitter
    d_in = DataNode(name="result_slot")
    emitter = EmitterNode(name="emit", sink_id="main_output")
    emitter.add_input(Port(name="data", source=d_in))
    
    # 2. Setup Reactor and Mock Executor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    reactor.register_node(d_in)
    reactor.register_node(emitter)
    
    # 3. Register Sink with a Future for synchronization
    # The Future acts as the signal from the Reactor to the external world
    result_future = asyncio.get_running_loop().create_future()
    reactor.register_sink("main_output", result_future.set_result)

    # 4. Start Reactor in a background task
    run_task = asyncio.create_task(reactor.run())
    
    # 5. Inject Initial Data to trigger the Emitter
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 6. Wait for the core work to be done (result emitted)
    # This is the key synchronization point.
    try:
        emitted_result = await asyncio.wait_for(result_future, timeout=1.0)
    except asyncio.TimeoutError:
        # If timeout, it means the Emitter never fired.
        reactor.stop()
        await run_task
        pytest.fail("Sink was never called. EmitterNode logic is likely broken.")
    
    # 7. Assert the emitted result
    assert emitted_result == "Hello World"

    # 8. Explicitly stop the reactor (External Lifecycle Control)
    reactor.stop()
    
    # 9. Await the run task to ensure it shut down cleanly
    await run_task
~~~~~

### 下一步建议
此修复解决了 `event_loop` fixture 的依赖问题。现在，我们应该能够通过所有测试，再次验证 `EmitterNode` 在新的解耦架构下的行为。

根据路线图，我们现在准备好进入 **阶段 5.C：编译器与策略层的最终集成**。第一步将是 **阶段 5.C.1：[Compiler] 编译器后端支持信令与生命周期注入**。我将准备一个计划，修改编译器后端，使其能够自动生成包含结果发射器 (`EmitterNode`) 和终止信号发射器 (`EmitterNode` 链式连接，模拟旧的终止行为) 的自治计算图。
