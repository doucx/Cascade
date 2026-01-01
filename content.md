好的，我们采纳该战略。现在开始实施。

## [WIP] fix(vm): Implement sequential signaling for intrinsic nodes

### 错误分析
测试 `test_reactor_emits_result_to_sink` 失败的根本原因是 `EmitterNode` 和 `TerminatorNode` 之间存在时序竞争。它们被设置为并行地消费同一个输入 `DataNode`，并且都需要获取一个有限的并发资源。
-   如果 `TerminatorNode` 先执行，Reactor 会停止，`EmitterNode` 没有机会运行，导致测试因无法获取结果而超时失败。
-   如果 `EmitterNode` 先执行，因为它是一个不经过 Executor 的“内在节点”，它不会发出 `ExecutionFinished` 事件来释放资源。这导致 `TerminatorNode` 永远等待资源，Reactor 无法停止，测试同样超时失败。

### 用户需求
修复 `EmitterNode` 和 `TerminatorNode` 之间的时序竞争问题，确保“发射数据”的操作总是在“终止运行”之前完成。

### 评论
这个修复是实现“全对称架构”中“显式因果关系”的关键一步。我们通过让内在节点（如 Emitter）像普通节点一样发出完成信号，将它们的执行也纳入了图的物理规则中，从而可以用拓扑结构来保证执行顺序，而不是依赖于不确定的调度时机。

### 目标
1.  修改 `Reactor._fire` 方法，使 `EmitterNode` 在完成其核心功能（调用 sink）后，能发出一个标准的 `ExecutionFinished` 事件，以触发下游节点。
2.  重写 `test_result_emission.py` 测试，构建一个串行拓扑 (`D_in -> Emitter -> D_signal -> Terminator`)，从物理上保证执行顺序。

### 基本原理
我们将重用 `Reactor` 现有的事件处理和路由机制。在 `_fire` 方法中，当一个 `EmitterNode` 被激发时：
1.  它会像之前一样消耗输入并调用注册的 Sink。
2.  **新增**: 它会立即为自己生成一个 `ExecutionFinished` 事件，并将一个信号令牌放入默认的 "result" 输出端口。
3.  这个事件会被 Reactor 的主循环捕获，并像处理任何普通任务的完成事件一样，将信号令牌路由到下游连接的 `DataNode`，从而安全地触发 `TerminatorNode`。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/lifecycle #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 Reactor 以支持内在节点信令

我们将修改 `_fire` 方法，让 `EmitterNode` 能够发出完成信号。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, TerminatorNode):
            self.stop()
            return
        
        if isinstance(node, EmitterNode):
            sink = self._sinks.get(node.sink_id)
            if sink:
                # Emitter assumes a single input token for simplicity
                # We find the first token from the consumed inputs
                input_token = next(iter(inputs.values()), None)
                if input_token:
                    sink(input_token.payload)
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~
~~~~~python.new
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, TerminatorNode):
            self.stop()
            # A terminator can also signal, e.g., to confirm shutdown.
            # For now, we assume it's the absolute end.
            return
        
        if isinstance(node, EmitterNode):
            sink = self._sinks.get(node.sink_id)
            if sink:
                # Emitter assumes a single input token for simplicity
                # We find the first token from the consumed inputs
                input_token = next(iter(inputs.values()), None)
                if input_token:
                    sink(input_token.payload)
            
            # CRITICAL: After emitting, fire a completion event to trigger downstream
            # nodes (like a chained terminator). We use the default 'result' output
            # as a signal port.
            signal_token = Token(payload=True, tag="default")
            self.push_event(ExecutionFinished(node=node, outputs={"result": signal_token}))
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

#### Acts 2: 重写测试以使用串行拓扑

现在，我们将测试用例修改为串行结构，消除竞争条件。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_result_emission.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, Token, Port, EmitterNode, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated
from cascade.runtime.resource_manager import ResourceManager

@pytest.mark.asyncio
async def test_reactor_emits_result_to_sink_sequentially():
    """
    Verifies that an EmitterNode correctly pushes data to a sink, and THEN
    a chained TerminatorNode successfully stops the reactor.
    
    Topology: D_in -> Emitter -> D_signal -> Terminator
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Sequential Topology
    d_in = DataNode(name="result_slot")
    d_signal = DataNode(name="signal_slot") # Connects Emitter and Terminator
    
    # Emitter: Reads from d_in, sends to "main_output", signals to d_signal
    emitter = EmitterNode(name="emit", sink_id="main_output")
    emitter.add_input(Port(name="data", source=d_in))
    emitter.add_output(Port(name="result", target=d_signal)) # Output for signaling
    
    # Terminator: Reads from d_signal, stops the reactor
    terminator = TerminatorNode(name="term")
    terminator.add_input(Port(name="signal", source=d_signal))
    
    reactor.register_node(d_in)
    reactor.register_node(d_signal)
    reactor.register_node(emitter)
    reactor.register_node(terminator)
    
    # 2. Register Sink
    result_future = asyncio.Future()
    reactor.register_sink("main_output", result_future.set_result)

    # 3. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 4. Inject Initial Data
    reactor.push_event(TokenGenerated(node=d_in, token=Token("Hello World")))
    
    # 5. Wait for Reactor to terminate on its own
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        # If timeout, it means the terminator was never reached.
        reactor.stop()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor did not terminate. The Emitter->Terminator signal chain is broken.")
    
    # 6. Verify Result from Sink
    try:
        result = result_future.result()
        assert result == "Hello World"
    except asyncio.InvalidStateError:
        pytest.fail("Sink was never called with the result, even though Reactor terminated.")
~~~~~

### 下一步建议
我们已经实现了 Reactor 的自我终止和结果发射机制，并且通过引入“内在节点信令”解决了它们之间的时序问题。这为构建一个完全由图拓扑控制生命周期的自治计算系统奠定了坚实的基础。

下一步（阶段 5.3），我们将把这些新能力集成到 `VMExecutionStrategy` 中，彻底重构其工作方式，使其从一个“微观管理者”转变为一个“点火器”。
