简要回答：
好的，我将为第二阶段“动力层实现”创建测试文件。这包括 `test_reactor_loop.py` 和 `test_routing.py`，旨在定义反应堆循环、事件处理及路由逻辑的行为。

## [WIP] test: Create Phase 2 Reactor and Routing tests

### 用户需求
根据 TDD 重构计划（Phase 2），创建 `cascade-vm` 包中关于 `Reactor` 核心循环和路由逻辑的测试文件。

### 评论
这些测试将定义 Cascade 新运行时的核心物理引擎行为。
1.  `test_reactor_loop.py`: 验证事件驱动的势能更新、任务分发和状态传播。
2.  `test_routing.py`: 验证基于 Token Tag 的动态路由（Switch/Jump）逻辑。

目前这些测试将处于 **RED** 状态（ImportError 或 AttributeError），因为对应的实现代码尚未编写。这符合 TDD 流程。

### 目标
1.  创建 `packages/cascade-vm/tests/reactor` 目录。
2.  创建 `packages/cascade-vm/tests/reactor/test_reactor_loop.py`。
3.  创建 `packages/cascade-vm/tests/reactor/test_routing.py`。

### 基本原理
我们正在实施“焦土式”重构，直接定义新架构的预期行为。通过先写测试，我们确立了 `Reactor` 作为“物理引擎”的契约：它必须响应事件，计算势能，并根据物理规则（如标签匹配）移动数据。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建测试目录
首先确保 `reactor` 测试目录存在。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/tests/reactor
~~~~~

#### Acts 2: 创建 `test_reactor_loop.py`
定义反应堆核心循环的测试用例：事件驱动、执行分发、状态传播。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_reactor_loop.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

# These imports will fail initially, which is expected for TDD RED state
from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, TokenGenerated, ExecutionFinished

@pytest.mark.asyncio
async def test_reactor_event_driven_potential_update():
    """
    Case 1 (Event Driven): 
    验证 Reactor 能够处理 TokenGenerated 事件并更新下游节点的势能。
    """
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1")
    # Wiring: d_node -> f_node
    f_node.add_input(Port(name="in1", source=d_node))
    
    # 2. Setup Reactor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    
    # Register nodes so Reactor tracks them
    reactor.register_node(d_node)
    reactor.register_node(f_node)
    
    # 3. Action: Simulate a token generation event
    token = Token(payload=42)
    event = TokenGenerated(node=d_node, token=token)
    
    # Push event (Reactor buffers it)
    reactor.push_event(event)
    
    # 4. Process one step of the reactor loop
    await reactor.step()
    
    # 5. Assertions
    # The data node should now hold the token
    assert d_node.peek() == token
    # The function node should be ready because its input is excited
    assert f_node.is_ready()
    # At this stage, we haven't triggered firing logic, just potential update verification
    # (Or if step() includes firing, verify executor calls in next test)


@pytest.mark.asyncio
async def test_reactor_execution_dispatch():
    """
    Case 2 (Execution Dispatch):
    构造 D_in -> F -> D_out 网络。
    验证当 D_in 激发时，Reactor 自动将 F 提交给 Executor。
    """
    # 1. Topology
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process")
    
    f_node.add_input(Port(name="arg", source=d_in))
    f_node.add_output(Port(name="res", target=d_out))
    
    # 2. Reactor
    mock_executor = AsyncMock()
    reactor = Reactor(executor=mock_executor)
    reactor.register_node(d_in)
    reactor.register_node(d_out)
    reactor.register_node(f_node)
    
    # 3. Inject Initial State via Event
    initial_token = Token(10)
    reactor.push_event(TokenGenerated(node=d_in, token=initial_token))
    
    # 4. Run Loop
    # Step should:
    # a. Process TokenGenerated -> Update D_in -> Update F potential
    # b. Detect F is ready -> Fire F -> Submit to Executor
    await reactor.step()
    
    # 5. Assertions
    assert mock_executor.submit.called
    
    call_args = mock_executor.submit.call_args
    # submit(node, inputs)
    submitted_node = call_args[0][0]
    submitted_inputs = call_args[0][1]
    
    assert submitted_node == f_node
    assert submitted_inputs["arg"].payload == 10
    
    # Verify atomicity: tokens should be consumed from input
    assert d_in.is_empty()


@pytest.mark.asyncio
async def test_reactor_propagation():
    """
    Case 3 (Propagation):
    验证 Executor 完成任务后，Reactor 能处理结果并将新 Token 放入下游节点。
    """
    # 1. Topology
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process")
    f_node.add_output(Port(name="res", target=d_out))
    
    reactor = Reactor(executor=AsyncMock())
    reactor.register_node(f_node)
    reactor.register_node(d_out)
    
    # 2. Simulate Executor finishing a task (callback or event)
    output_tokens = {"res": Token(20)}
    event = ExecutionFinished(node=f_node, outputs=output_tokens)
    
    reactor.push_event(event)
    
    # 3. Process
    await reactor.step()
    
    # 4. Assertions
    assert d_out.is_excited()
    assert d_out.peek().payload == 20
~~~~~

#### Acts 3: 创建 `test_routing.py`
定义路由逻辑测试：基于 Tag 的通道过滤。

~~~~~act
write_file
packages/cascade-vm/tests/reactor/test_routing.py
~~~~~
~~~~~python
import pytest
from unittest.mock import AsyncMock
from cascade.spec.physics import DataNode, FuncNode, Token, Port
from cascade.vm.reactor import Reactor, ExecutionFinished, Channel

@pytest.mark.asyncio
async def test_routing_tag_matching():
    """
    Case 1: Tag Matching & Routing
    验证 Reactor 根据 Token 的 tag 正确选择 Channel。
    
    拓扑: F -> (Tag='default') -> D_next
         F -> (Tag='continue') -> D_loop
    """
    # 1. Topology
    f_node = FuncNode(name="decision")
    d_next = DataNode(name="next")
    d_loop = DataNode(name="loop")
    
    # 2. Define Channels (The edges of the Bipartite Graph)
    # Channel connects a specific output port of a FuncNode to a DataNode, with a filter.
    c_default = Channel(
        source=f_node, 
        target=d_next, 
        output_name="result", 
        tag_filter="default"
    )
    
    c_loop = Channel(
        source=f_node, 
        target=d_loop, 
        output_name="result", 
        tag_filter="continue"
    )
    
    # 3. Setup Reactor
    reactor = Reactor(executor=AsyncMock())
    # We assume Reactor manages topology (channels)
    reactor.register_channel(c_default)
    reactor.register_channel(c_loop)
    
    # 4. Simulate F producing a 'continue' token
    token = Token(payload=1, tag="continue")
    
    # The Executor would emit this event
    event = ExecutionFinished(node=f_node, outputs={"result": token})
    reactor.push_event(event)
    
    # 5. Step
    await reactor.step()
    
    # 6. Assertions
    # D_loop should receive the token because tags match
    assert d_loop.is_excited()
    assert d_loop.peek() == token
    
    # D_next should remain empty because 'continue' != 'default'
    assert d_next.is_empty()


@pytest.mark.asyncio
async def test_routing_fan_out_same_tag():
    """
    Case 2: Broadcasting
    验证同一个 Tag 可以被多个 Channel 接收 (Fan-out)。
    """
    f_node = FuncNode(name="broadcast")
    d_1 = DataNode(name="d1")
    d_2 = DataNode(name="d2")
    
    # Both channels accept 'default'
    c1 = Channel(source=f_node, target=d_1, output_name="out", tag_filter="default")
    c2 = Channel(source=f_node, target=d_2, output_name="out", tag_filter="default")
    
    reactor = Reactor(executor=AsyncMock())
    reactor.register_channel(c1)
    reactor.register_channel(c2)
    
    token = Token(payload="msg", tag="default")
    event = ExecutionFinished(node=f_node, outputs={"out": token})
    reactor.push_event(event)
    
    await reactor.step()
    
    # Both should receive the token (Copy semantics for broadcast)
    assert d_1.peek().payload == "msg"
    assert d_2.peek().payload == "msg"
~~~~~

### 下一步建议
测试文件创建完毕。下一步是执行这些测试，确认它们因为缺少 `cascade.vm.reactor` 模块而失败（RED），然后开始实现 `Reactor` 类及其辅助结构（如 `Channel`）。
