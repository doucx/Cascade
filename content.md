## [WIP] feat(engine): 在 LocalExecutor 中实现同步任务的自动线程卸载

### 用户需求
根据建议书的第一点，我们需要实现对同步任务的“隐式卸载”。这意味着当 `Executor` 遇到一个普通的同步函数 (`def`) 时，不应直接在当前的事件循环线程中运行它（这会阻塞整个引擎），而应将其放到一个独立的线程中运行。

### 错误分析
当前的测试失败 `AssertionError: Async task finished at ..., which is after Sync task ...` 证实了在现有的实现中，同步任务 (`time.sleep(0.2)`) 阻塞了事件循环，导致并发的异步任务 (`asyncio.sleep(0.1)`) 只能在同步任务完成后才开始执行，从而出现了异步任务反而比同步任务结束得晚的现象。

### 评论
这个修复是 Cascade 向“高性能运行时”迈进的一大步。它利用 Python 的 `asyncio.to_thread`（或等价机制）来自动管理阻塞操作，使得用户无需深入理解异步编程的细节（如 `run_in_executor`），就能写出高性能的混合工作流。这也符合我们“降低认知负担”的设计哲学。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/adapters/executors/local.py`。
2.  引入 `asyncio` 模块。
3.  在 `execute` 方法中，利用 `node.is_async` 标志进行分支处理：
    *   如果是异步节点，保持原有的 `await` 调用。
    *   如果是同步节点，使用 `await asyncio.to_thread(node.callable_obj, *args, **kwargs)` 进行执行。

### 基本原理
`asyncio.to_thread` 会在一个独立的线程中运行提供的函数，并返回一个协程。这允许主事件循环在等待线程完成的同时，继续处理其他协程（如我们的异步任务、心跳检测、IO回调等）。这样，`time.sleep(0.2)` 只会阻塞那个工作线程，而不会阻塞主循环，从而实现了真正的并行。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/perf #scope/dx #ai/instruct #task/domain/execution #task/object/local-executor #task/action/implement-offloading #task/state/continue

---

### Script

#### Acts 1: 修改 LocalExecutor 以支持隐式卸载

我们将更新 `LocalExecutor`，使其能够区分同步和异步任务，并将同步任务自动分派到线程池中。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            result = node.callable_obj(*args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, List
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.graph.exceptions import StaticGraphError


class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        """
        Executes a single node's callable object with the provided arguments.
        """
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            # Implicit Offloading:
            # Synchronous tasks are offloaded to a separate thread to prevent blocking
            # the main asyncio event loop. This allows async tasks and IO operations
            # to run concurrently with CPU-bound or blocking sync tasks.
            result = await asyncio.to_thread(node.callable_obj, *args, **kwargs)

        # Runtime guard against the "task returns LazyResult" anti-pattern.
        if isinstance(result, (LazyResult, MappedLazyResult)):
~~~~~

### 下一步建议
代码修改完成后，我们将再次运行 `tests/engine/e2e/test_offloading.py`。这一次，我们预期：
1.  异步任务将先于同步任务完成（因为它只需要 0.1s，且不再被阻塞）。
2.  测试将通过 (GREEN)。
3.  这标志着 P0 级任务“关于引入‘计算与 IO 隔离’调度语法糖的建议书”的第一阶段目标达成。

接下来，我们将考虑建议书中的其他优化点，如“语义化调度标签”或“开发者诊断辅助”，但首先要确保这个核心功能稳固。
