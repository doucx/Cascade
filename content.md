好的，我们正式启动 **阶段 5.B：原生物理执行器与生命周期解耦**。

第一步是创建 `PhysicsExecutor`，这是将 `Reactor` 与旧执行引擎彻底解耦的关键组件。它将作为一个纯粹的适配器，负责接收 `Reactor` 的执行请求，调用 `symbol_table` 中的 Python 函数，并将结果以事件的形式报告回 `Reactor`。

我将遵循 TDD 流程，首先创建定义其行为契约的测试文件，然后编写实现代码使其通过。

## [WIP] feat(vm): 创建 PhysicsExecutor 以解耦 Reactor 的执行逻辑

### 用户需求
根据 [路线图：全对称物理引擎与编译器重构](深度重构/路线图：全对称物理引擎与编译器重构.md)，我们需要创建一个新的 `PhysicsExecutor` 类，作为 `Reactor` 和具体函数执行之间的桥梁。

### 评论
这是实现 `Reactor` 架构纯粹性的关键一步。通过引入一个专用的 `PhysicsExecutor`，`Reactor` 本身可以完全专注于物理模拟（令牌流动、势能计算），而将“如何调用 Python 函数”这一实现细节委托出去。这极大地增强了系统的模块化和可测试性，是我们走向一个完全自包含的、与旧引擎无关的 `cascade-vm` 包的核心里程碑。

### 目标
1.  创建 `cascade.vm.executors.physics.PhysicsExecutor` 类。
2.  实现其 `submit` 方法，使其能够处理同步和异步任务的执行及异常。
3.  创建对应的单元测试，确保 `PhysicsExecutor` 的行为符合预期。

### 基本原理
我们将采用依赖注入模式。`PhysicsExecutor` 在初始化时接收 `reactor` 和 `symbol_table`。当其 `submit` 方法被调用时，它会：
1.  **链接 (Link)**: 使用 `node` 的标识符从 `symbol_table` 中查找对应的 Python 可调用对象。
2.  **解包 (Unpack)**: 从输入的 `Token` 字典中提取 `payload` 作为函数参数。
3.  **执行 (Execute)**: 调用函数，并正确处理同步和异步两种情况。
4.  **报告 (Report)**: 将执行结果或异常封装在一个 `ExecutionFinished` 事件中，并通过注入的 `reactor` 实例推回事件队列。

这种清晰的单向数据流确保了 `Reactor` 和 `Executor` 之间的松耦合关系。

### 标签
#intent/build #flow/ready #priority/high
#comp/engine #concept/executor #scope/core #dx
#ai/instruct
#task/domain/vm #task/object/physics-executor #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 创建目录结构

我们首先为新的执行器及其测试创建必要的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm/executors
mkdir -p packages/cascade-vm/tests/unit/executors
~~~~~

#### Acts 2: [TDD-RED] 编写 PhysicsExecutor 的测试用例

我们创建测试文件 `test_physics.py`。这个测试将定义 `PhysicsExecutor` 的完整行为契约，包括成功路径、失败路径以及对同步/异步函数的支持。在实现代码前，这个测试会因为找不到 `PhysicsExecutor` 模块而失败。

~~~~~act
write_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock

# These imports will fail initially, which is the point of TDD RED state
from cascade.vm.executors.physics import PhysicsExecutor
from cascade.spec.physics import FuncNode, Token
from cascade.vm.reactor.events import ExecutionFinished

# --- Mocks and Fixtures ---

@pytest.fixture
def mock_reactor():
    """A mock reactor with a push_event method."""
    reactor = MagicMock()
    reactor.push_event = MagicMock()
    return reactor

@pytest.fixture
def mock_symbol_table():
    """A mock symbol table mapping node names to callables."""
    def sync_add(a, b):
        return a + b
    
    async def async_add(a, b):
        await asyncio.sleep(0)
        return a + b
        
    def sync_fail(a, b):
        raise ValueError("Sync failure")
        
    async def async_fail(a, b):
        raise ValueError("Async failure")

    return {
        "sync_add_hash": sync_add,
        "async_add_hash": async_add,
        "sync_fail_hash": sync_fail,
        "async_fail_hash": async_fail,
    }

# --- Test Cases ---

@pytest.mark.asyncio
async def test_physics_executor_submit_sync_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly find and execute a synchronous task,
    unpacking token payloads and pushing a successful ExecutionFinished event.
    """
    # 1. Setup
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="sync_add_hash") # Using name as hash for simplicity in test
    inputs = {
        "a": Token(payload=10),
        "b": Token(payload=20)
    }

    # 2. Action
    await executor.submit(node, inputs)

    # 3. Assertions
    # Verify that the reactor received the correct completion event
    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event, ExecutionFinished)
    assert event.node == node
    assert event.error is None
    
    # The result should be a new Token
    result_token = event.outputs.get("result")
    assert isinstance(result_token, Token)
    assert result_token.payload == 30
    assert result_token.tag == "default"


@pytest.mark.asyncio
async def test_physics_executor_submit_async_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly execute an asynchronous task.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="async_add_hash")
    inputs = {"a": Token(5), "b": Token(5)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]
    
    assert event.outputs["result"].payload == 10

@pytest.mark.asyncio
async def test_physics_executor_handles_sync_failure(mock_reactor, mock_symbol_table):
    """
    Tests that if a synchronous task fails, an ExecutionFinished event with an
    error is pushed to the reactor.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="sync_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event, ExecutionFinished)
    assert event.node == node
    assert isinstance(event.error, ValueError)
    assert str(event.error) == "Sync failure"
    assert not event.outputs # No output on failure

@pytest.mark.asyncio
async def test_physics_executor_handles_async_failure(mock_reactor, mock_symbol_table):
    """
    Tests failure handling for asynchronous tasks.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="async_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)

    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]

    assert isinstance(event.error, ValueError)
    assert str(event.error) == "Async failure"

@pytest.mark.asyncio
async def test_physics_executor_handles_missing_function(mock_reactor, mock_symbol_table):
    """
    Tests that a linking error (function not in symbol table) is reported.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)
    
    node = FuncNode(name="missing_hash")
    inputs = {}

    await executor.submit(node, inputs)
    
    mock_reactor.push_event.assert_called_once()
    event = mock_reactor.push_event.call_args[0][0]
    
    assert isinstance(event.error, RuntimeError)
    assert "Linking failed" in str(event.error)
~~~~~

#### Acts 3: [TDD-GREEN] 创建 PhysicsExecutor 实现

现在，我们创建 `PhysicsExecutor` 的实现文件。这段代码将满足上一阶段测试文件定义的所有契约，使测试套件进入绿色状态。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/executors/__init__.py
~~~~~
~~~~~python
from .physics import PhysicsExecutor

__all__ = ["PhysicsExecutor"]
~~~~~
~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/executors/physics.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, Callable

from cascade.spec.physics import FuncNode, Token
from cascade.vm.reactor.events import ExecutionFinished

# A stand-in for the Reactor protocol for type hinting
ReactorProtocol = Any 

class PhysicsExecutor:
    """
    A native executor for the physics-based VM. It links a FuncNode from the
    topology to a concrete Python function via the symbol table and executes it.
    """

    def __init__(self, reactor: ReactorProtocol, symbol_table: Dict[str, Callable]):
        self._reactor = reactor
        self._symbol_table = symbol_table

    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """
        Executes the logic for a given FuncNode and reports the result back
        to the reactor.
        """
        outputs = {}
        error = None

        try:
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )

            # 2. Unpack Payloads: Convert Dict[str, Token] to Dict[str, Any]
            kwargs = {name: token.payload for name, token in inputs.items()}

            # 3. Execution
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            
            # 4. Wrap Result: Convert the raw result back into a Token.
            # For now, we assume a single 'result' output port with 'default' tag.
            outputs["result"] = Token(payload=result, tag="default")

        except Exception as e:
            error = e
        
        # 5. Report: Push an ExecutionFinished event to the reactor.
        event = ExecutionFinished(node=node, outputs=outputs, error=error)
        self._reactor.push_event(event)
~~~~~

#### Acts 4: 将新执行器导出到顶层 `vm` 模块

最后，我们将新的 `PhysicsExecutor` 添加到 `cascade.vm` 的 `__init__.py` 中，使其可以被 `VMExecutionStrategy` 等外部组件方便地导入。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/__init__.py
~~~~~
~~~~~python.old
from .protocols import ResourceManager, ConstraintManager

__all__ = ["VirtualMachine", "Frame", "ResourceManager", "ConstraintManager"]
~~~~~
~~~~~python.new
from .protocols import ResourceManager, ConstraintManager
from .executors import PhysicsExecutor

__all__ = [
    "VirtualMachine",
    "Frame",
    "ResourceManager",
    "ConstraintManager",
    "PhysicsExecutor",
]
~~~~~

### 下一步建议
我们已经成功创建了 `PhysicsExecutor`。根据路线图，下一步是 **阶段 5.B.2：[Spec & VM] 废除 `TerminatorNode`**。我将准备一个计划来从 `cascade-spec` 和 `cascade-vm` 中移除所有与 `TerminatorNode` 相关的定义和特殊逻辑。
