好的，你提供的这个 Traceback 非常清晰，它精确地指出了我们预料到的下一个必然会发生的问题。

## [WIP] fix(vm): 实现智能分发以支持异步 IC

### 错误分析
你的分析完全正确。错误 `ValueError: ... got <class 'coroutine'>` 的根本原因在于：

1.  **成功的异步化**：在我们上一个计划中，我们成功地将 `standard_bleacher` 等 IC 函数转换为了 `async def`。
2.  **执行器的不匹配**：`PhysicsExecutor` 被设计用来在**线程池**中运行**同步阻塞**函数。当你给它一个 `async def` 函数时，它仅仅是“调用”它，而调用一个协程函数会立即返回一个**协程对象 (coroutine object)**，并不会执行其内部代码。
3.  **错误的返回值**：因此，`executor.submit` 正确地返回了这个协程对象。`Reactor` 的 `_fire` 方法接收到这个对象，发现它不是预期的 `Dict[str, Token]`，于是抛出了类型错误。

我们成功地升级了“标准元器件 (`cascade-std`)”，但现在必须升级使用这些元器件的“底层物理定律 (`Reactor`)”来适配它们。

### 用户需求
修改 `Reactor` 的执行逻辑，使其能够“智能地”识别一个 IC 函数是同步的还是异步的，并采用正确的执行方式。

### 评论
这是一个关键的修复，它将我们上一个重构计划的理论优势转化为实际的性能收益。通过实现智能分发，我们创建了一个混合执行模型，它既能以零开销的方式在事件循环上运行原生异步任务，又能安全地将旧的或CPU密集型的同步任务卸载到线程池，实现了两全其美。

### 目标
1.  在 `packages/cascade-vm/src/cascade/vm/reactor.py` 文件中导入 `inspect` 模块。
2.  修改 `Reactor._fire` 方法。
3.  在调用函数前，使用 `inspect.iscoroutinefunction()` 检查其类型。
4.  如果函数是异步的 (`async def`)，则直接 `await func(...)`。
5.  如果函数是同步的 (`def`)，则继续使用现有的 `await self.executor.submit(...)` 路径。

### 基本原理
我们将采用“智能分发”（Smart Dispatch）模式。`Reactor` 作为调用方，有责任检查它要调用的函数（来自 `function_map`）的性质。Python 的 `inspect` 模块提供了 `iscoroutinefunction`，这是一个完美的、零成本的工具，可以在运行时进行这种反射检查。通过在 `_fire` 方法中加入一个简单的 `if/else` 分支，我们就可以无缝地桥接 `asyncio` 事件循环和 `ThreadPoolExecutor`，使 `Reactor` 能够正确处理任何类型的可调用对象。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/vm #concept/executor #scope/core
#ai/instruct
#task/state/continue

---

### Script

#### Acts 1: 在 Reactor 中实现智能分发

我们将修改 `Reactor._fire` 方法，使其能够根据 IC 函数是 `def`还是 `async def` 来选择正确的执行策略。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
import asyncio
from typing import List, Callable, Dict, Tuple
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor


class Reactor:
~~~~~
~~~~~python.new
import asyncio
import inspect
from typing import List, Callable, Dict, Tuple
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor


class Reactor:
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # We pass the node instance as the second argument to the instruction
        # to allow access to static port definitions (PortDef).
        result_tokens: Dict[str, Token] = await self.executor.submit(
            func, (input_data, node)
        )

        if not isinstance(result_tokens, dict):
            raise ValueError(
                f"Function for node {node.id} must return a Dict[str, Token], "
                f"got {type(result_tokens)}"
            )
~~~~~
~~~~~python.new
        # We pass the node instance as the second argument to the instruction
        # to allow access to static port definitions (PortDef).
        if inspect.iscoroutinefunction(func):
            # Natively await async functions
            result_tokens = await func(input_data, node)
        else:
            # Offload sync functions to the thread pool
            result_tokens = await self.executor.submit(func, (input_data, node))

        if not isinstance(result_tokens, dict):
            raise ValueError(
                f"Function for node {node.id} must return a Dict[str, Token], "
                f"got {type(result_tokens)}"
            )
~~~~~

### 下一步建议
我们已经修复了 `Reactor` 的核心逻辑。现在，请重新运行 `test_resource_backpressure.py` 和整个测试套件。我预期所有测试都应该通过，我们的系统将达到一个功能正确且性能优化的“绿色”状态。

一旦所有测试通过，我们就可以将这两个 `[WIP]` 计划合并成一个逻辑上的提交。我建议下一步是创建一个 `[COMMIT]` 计划来固化我们的成果。
