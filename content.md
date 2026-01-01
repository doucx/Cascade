简要回答：
好的，进入阶段 5.1.2。我将实现 `TerminatorNode` 的运行时表示及其在 Reactor 中的逻辑。

## [WIP] feat(vm): Implement TerminatorNode logic

### 用户需求
1.  在 `cascade.spec.physics` 中定义运行时的 `TerminatorNode`。
2.  在 `Reactor._fire` 中实现对 `TerminatorNode` 的处理，使其触发 `stop()`。
3.  修复并启用 `test_autonomous_lifecycle.py` 中的测试。

### 评论
通过在物理层（`physics`）引入 `TerminatorNode`，我们将“停止”动作变成了图中的一个物理事件。这消除了 Reactor 对外部控制信号的依赖，使其成为一个闭环系统。

### 目标
1.  修改 `packages/cascade-spec/src/cascade/spec/physics.py`。
2.  修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py`。
3.  更新 `packages/cascade-vm/tests/reactor/test_autonomous_lifecycle.py`。

### 基本原理
-   **物理定义**: `TerminatorNode` 继承自 `FuncNode`，但在语义上它是能量的终点。
-   **Reactor 逻辑**: 当 Reactor 准备激发一个节点时，如果该节点是 `TerminatorNode`，则立即停止主循环。这比将其提交给 Executor 再等待结果更高效且符合直觉（“一旦接触终结者，时间停止”）。
-   **测试修复**: 之前的测试因 `asyncio.wait_for` 的取消机制引发了未捕获的 `CancelledError`。我们将完善测试的异常处理逻辑。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/spec #concept/lifecycle #task/domain/runtime #task/object/terminator #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 定义运行时 TerminatorNode

在 `cascade.spec.physics` 中添加 `TerminatorNode` 类。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def produce_outputs(self, tokens: Dict[str, Token]):
        """
        Push result tokens to output targets.
        """
        for name, token in tokens.items():
            if name in self.outputs:
                port = self.outputs[name]
                if port.target:
                    port.target.put(token)
~~~~~
~~~~~python.new
    def produce_outputs(self, tokens: Dict[str, Token]):
        """
        Push result tokens to output targets.
        """
        for name, token in tokens.items():
            if name in self.outputs:
                port = self.outputs[name]
                if port.target:
                    port.target.put(token)


class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    pass
~~~~~

#### Acts 2: 实现 Reactor 的自杀逻辑

修改 `Reactor._fire` 方法，检测 `TerminatorNode` 并触发停止。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
from typing import Deque, Set, List, Dict, Any, Optional
from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
~~~~~
~~~~~python.new
from typing import Deque, Set, List, Dict, Any, Optional
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~
~~~~~python.new
    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Special Case: Terminator
        if isinstance(node, TerminatorNode):
            self.stop()
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

#### Acts 3: 修复并完善测试

更新测试用例以使用新的 `TerminatorNode` 类，并修复 `CancelledError` 问题。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_autonomous_lifecycle.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import AsyncMock

from cascade.spec.physics import DataNode, FuncNode, Token, Port, TerminatorNode
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished
from cascade.runtime.resource_manager import ResourceManager

# --- Helpers ---

def create_simple_chain():
    """Creates a simple D -> F -> D chain."""
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", resource_requirements={"slots": 1})
    
    f_node.add_input(Port(name="arg", source=d_in))
    f_node.add_output(Port(name="res", target=d_out))
    
    return [f_node], [d_in, d_out]

# --- Tests ---

@pytest.mark.asyncio
async def test_reactor_runs_forever_without_terminator():
    """
    Verifies the default behavior: The Reactor run loop does NOT exit automatically
    when the graph becomes idle. It waits indefinitely for new events.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup minimal topology
    func_nodes, data_nodes = create_simple_chain()
    for n in func_nodes + data_nodes:
        reactor.register_node(n)
        
    # 2. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 3. Inject work
    reactor.push_event(TokenGenerated(node=data_nodes[0], token=Token(1)))
    
    # 4. Mock executor completion
    async def side_effect(node, inputs):
        reactor.push_event(ExecutionFinished(node=node, outputs={}))
    mock_executor.submit.side_effect = side_effect
    
    # 5. Wait and Expect Timeout
    # wait_for will cancel run_task on timeout
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(run_task, timeout=0.2)
        
    # Cleanup: Ensure task is cancelled/stopped properly
    reactor.stop()
    try:
        await run_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_reactor_terminates_via_terminator_node():
    """
    Verifies the "Suicide Pact":
    When a TerminatorNode is fired, the Reactor should call stop() on itself
    and the run() loop should return.
    """
    rm = ResourceManager(capacity={"slots": 1})
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor, resource_manager=rm)
    
    # 1. Setup Topology: DataNode -> Terminator
    d_in = DataNode(name="trigger")
    terminator = TerminatorNode(name="term", resource_requirements={"slots": 1})
    terminator.add_input(Port(name="signal", source=d_in))
    
    reactor.register_node(d_in)
    reactor.register_node(terminator)
    
    # 2. Start Reactor
    run_task = asyncio.create_task(reactor.run())
    
    # 3. Trigger the terminator
    reactor.push_event(TokenGenerated(node=d_in, token=Token("DIE")))
    
    # 4. Expectation: The run loop should exit gracefully WITHOUT timeout
    # If it times out, the logic is broken.
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except asyncio.TimeoutError:
        reactor.stop()
        try:
            await run_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Reactor failed to terminate automatically upon triggering TerminatorNode")
    
    # Assert stop was called (run loop exited)
    assert run_task.done()
    assert not run_task.cancelled()
~~~~~

### 下一步建议
如果测试通过（GREEN），我们将进入阶段 5.2，处理数据的“发射”问题，因为单纯的终止还不够，我们还需要能从这个闭环系统中拿出结果。我们将实现 `EmitterNode`。
