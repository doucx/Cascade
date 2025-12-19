好的，这是一个绝佳的重构步骤，完全符合 **DRY (Don't Repeat Yourself)** 原则。我们将 E2E 测试的脚手架 (`harness.py`) 更新为使用我们刚刚创建的、更健壮的 `LocalBusConnector`。

为了确保现有的大量 E2E 测试用例不受影响，我们将使用一个简单的别名 (`InProcessConnector = LocalBusConnector`) 来维持向后兼容性。

## [WIP] refactor(tests): Consolidate E2E harness to use LocalBusConnector

### 用户需求
将 `tests/py/e2e/harness.py` 中 `InProcessConnector` 的实现替换为对新创建的 `cascade.connectors.local.LocalBusConnector` 的引用，以消除重复代码。

### 评论
这是一个标准的、健康的重构。它将测试基础设施与生产代码对齐，确保我们的测试环境与本地运行环境使用完全相同的内存总线实现。这不仅减少了维护成本，也增强了测试的有效性。通过别名维持兼容性是一种低风险、高收益的策略。

### 目标
1.  修改 `tests/py/e2e/harness.py` 文件。
2.  移除 `InProcessConnector` 的本地实现。
3.  导入 `LocalBusConnector` 并将其别名为 `InProcessConnector`。

### 基本原理
我们已经验证了 `LocalBusConnector` 的行为符合我们的 TDD 规范，它现在是内存消息总线的“事实标准”。测试脚手架作为该组件的用户，理应直接使用这个标准实现，而不是维护一个功能重复的副本。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/tests #comp/runtime #concept/telemetry #scope/dx
#task/domain/testing #task/object/test-harness #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 重构 `harness.py`

我们将 `InProcessConnector` 的完整类定义替换为一个导入和别名。

~~~~~act
patch_file
tests/py/e2e/harness.py
~~~~~
~~~~~python
from typing import List
from cascade.interfaces.protocols import Connector, Executor
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class MockWorkExecutor(Executor):
    """Executor that simulates short, time-consuming work."""

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Yield control to event loop to simulate async boundary
        await asyncio.sleep(0)
        if kwargs:
            return next(iter(kwargs.values()))
        return "done"


class InProcessConnector(Connector):
    """
    A deterministic, in-memory connector that simulates an MQTT broker with
    retained message support for robust E2E testing.
    """

    _shared_topics: Dict[str, List[asyncio.Queue]] = defaultdict(list)
    _retained_messages: Dict[str, Any] = {}

    def __init__(self):
        # Clear state for each test instance to ensure isolation
        self._shared_topics.clear()
        self._retained_messages.clear()
        self._is_connected = True

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        if not self._is_connected:
            return

        if retain:
            if payload != {}:  # An empty dict payload is a resume/clear command
                self._retained_messages[topic] = payload
            elif topic in self._retained_messages:
                del self._retained_messages[topic]

        for sub_topic, queues in self._shared_topics.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                for q in queues:
                    await q.put((topic, payload))

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        queue = asyncio.Queue()
        self._shared_topics[topic].append(queue)

        # Immediately deliver retained messages that match the subscription.
        # We await the callback to ensure state is synchronized before proceeding.
        for retained_topic, payload in self._retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                await callback(retained_topic, payload)

        asyncio.create_task(self._listen_on_queue(queue, callback))

    async def _listen_on_queue(self, queue: asyncio.Queue, callback):
        while self._is_connected:
            try:
                topic, payload = await asyncio.wait_for(queue.get(), timeout=0.1)
                await callback(topic, payload)
                queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        """
        Checks if a concrete topic matches a subscription pattern (supporting + and #).
        """
        sub_parts = subscription.split("/")
        topic_parts = topic.split("/")

        for i, sub_part in enumerate(sub_parts):
            if sub_part == "#":
                # '#' matches the rest of the topic, so it's a match
                return True

            if i >= len(topic_parts):
                # Topic is shorter than subscription pattern (and not matched by #)
                return False

            topic_part = topic_parts[i]

            if sub_part == "+":
                # '+' matches any single level, so we continue to the next part
                continue

            if sub_part != topic_part:
                # Literal parts do not match
                return False

        # If we finished the loop, it's a match IFF the lengths are the same.
        # (The '#' case is handled inside the loop)
        return len(sub_parts) == len(topic_parts)
~~~~~
~~~~~python
from typing import List
from cascade.connectors.local import LocalBusConnector
from cascade.interfaces.protocols import Connector, Executor
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class MockWorkExecutor(Executor):
    """Executor that simulates short, time-consuming work."""

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        # Yield control to event loop to simulate async boundary
        await asyncio.sleep(0)
        if kwargs:
            return next(iter(kwargs.values()))
        return "done"


# Alias for backward compatibility with existing e2e tests
InProcessConnector = LocalBusConnector
~~~~~

### 下一步建议
重构完成后，建议运行完整的 E2E 测试套件 (`pytest tests/py/e2e/`)，以确保我们的别名策略确实无缝地维持了兼容性。

如果所有测试通过，我们就正式完成了 **里程碑 1.1**，可以昂首进入 **里程碑 1.2**：对引擎核心进行改造，以支持永续递归。
