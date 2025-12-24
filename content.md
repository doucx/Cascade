好的，我们立即实施战略转向。

我将生成一个计划，该计划精确地执行我们刚才商定的修复策略：移除 `InMemoryStateBackend` 中不必要的 `asyncio.to_thread` 调用，以恢复其应有的高性能，同时保留 `RedisStateBackend` 中正确的线程隔离用法。

## [WIP] perf(engine): 优化 InMemoryStateBackend 以消除 to_thread 开销

### 错误分析
在将 `StateBackend` 异步化后，我们对 `InMemoryStateBackend` 应用了 `asyncio.to_thread`。性能剖析显示，这引入了巨大的线程协调开销，导致 TCO 快速路径的性能从 ~59k TPS 急剧下降到 ~5.5k TPS。根本原因是，我们将一个非阻塞的、纳秒级的内存操作（字典访问）错误地当作了阻塞 I/O 来处理。

### 用户需求
根据新的战略决议，恢复 `InMemoryStateBackend` 的性能，同时保留 `StateBackend` 协议的异步契约。

### 评论
这是一个关键的性能修复和架构原则精炼。它纠正了对“非阻塞”原则的过度概括，明确区分了“线程协调开销”和“真实 I/O 阻塞”。此次修复将使我们的 TCO 基准测试恢复到正常水平，同时保留了整个异步化重构的核心价值。

### 目标
1.  修改 `InMemoryStateBackend`，移除所有 `asyncio.to_thread` 调用。
2.  保持其 `async def` 方法签名，但使其内部操作直接同步执行。
3.  添加架构注释，解释为何此处不使用 `to_thread`，以防止未来的回归。

### 基本原理
`InMemoryStateBackend` 的字典操作是纯 CPU 绑定且速度极快，不会对 `asyncio` 事件循环构成实际的阻塞威胁。通过将其实现为简单的异步函数（直接返回值或执行操作），我们以最小的函数调用开销满足了 `async` 协议，同时避免了重量级的线程上下文切换，从而恢复了其作为高性能内存后端的本质。

### 标签
#intent/refine #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/core #task/object/state-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `InMemoryStateBackend` 并添加架构注释

我们将重写 `in_memory.py` 文件，移除 `asyncio.to_thread` 并添加解释性注释。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional


class InMemoryStateBackend:
    """
    An in-memory implementation of the StateBackend protocol using Python dictionaries.
    This is the default backend for local, single-process runs.

    ARCHITECTURAL NOTE on ASYNC IMPLEMENTATION:
    This class adheres to the `async def` contract of the StateBackend protocol,
    but it does NOT use `asyncio.to_thread`. This is an intentional performance
    optimization.

    Dictionary operations are synchronous but are pure-CPU and extremely fast
    (nanosecond-scale). They do not perform blocking I/O. Using `to_thread`
    would introduce significant overhead (context switching, thread pool management)
    for a non-existent problem, crippling performance in high-throughput scenarios
    like TCO fast paths.

    This implementation provides a compliant async interface with minimal overhead,
    making it suitable for its primary role as a high-performance, single-process backend.
    """

    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, node_id: str, result: Any) -> None:
        self._results[node_id] = result

    async def get_result(self, node_id: str) -> Optional[Any]:
        return self._results.get(node_id)

    async def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        self._skipped[node_id] = reason

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)

    async def clear(self) -> None:
        """
        Clears all results and skip reasons. Used between TCO iterations.
        """
        self._results.clear()
        self._skipped.clear()
~~~~~

#### Acts 2: 验证并修复 `test_in_memory_state.py`

由于我们不再使用 `to_thread`，相关的测试也必须更新。我们将移除对 `to_thread` 的 mock，保留功能性测试。

~~~~~act
patch_file
tests/engine/adapters/state/test_in_memory_state.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import patch, ANY
from cascade.adapters.state.in_memory import InMemoryStateBackend


@pytest.mark.asyncio
async def test_in_memory_uses_to_thread():
    """
    Verifies that InMemoryStateBackend uses asyncio.to_thread for its operations,
    ensuring compliance with the non-blocking I/O contract even for dict operations.
    """
    backend = InMemoryStateBackend("test_run")

    # We patch asyncio.to_thread in the module where the backend is defined
    with patch("cascade.adapters.state.in_memory.asyncio.to_thread") as mock_to_thread:
        # We need to make the mock awaitable because the method awaits it
        async def async_mock(*args, **kwargs):
            return "mocked_result"

        mock_to_thread.side_effect = async_mock

        # Test put_result
        await backend.put_result("node_1", "data")
        mock_to_thread.assert_called_with(ANY, "node_1", "data")

        # Test get_result
        await backend.get_result("node_1")
        mock_to_thread.assert_called_with(ANY, "node_1")


@pytest.mark.asyncio
async def test_in_memory_functional():
~~~~~
~~~~~python
import pytest
from cascade.adapters.state.in_memory import InMemoryStateBackend


@pytest.mark.asyncio
async def test_in_memory_functional():
~~~~~

### 下一步建议
我们已经完成了对性能回归的修复。现在 `InMemoryStateBackend` 既符合异步协议，又具备应有的高性能。

我强烈建议您再次运行 `observatory/benchmarks/tco_performance.py` 基准测试，以验证性能是否已恢复到预期水平。如果基准测试通过，那么这次重大的架构重构和随后的性能修复就可以被认为已圆满完成。之后，我将为您生成一个 `[COMMIT]` 计划。
