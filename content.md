是的，这是一个极好的重构方向。

我们将 `harness.py` 中的组件分拆处理：
1.  **`ControllerTestApp`**: 这是一个通用的、与实现无关的控制平面测试工具。它应该被提升到 `cascade.testing` 中，这样用户也可以方便地测试他们工作流的暂停/恢复逻辑。
2.  **`InProcessConnector`**: 这实际上是 `LocalBusConnector` 的别名。鉴于我们刚才发现它在特定测试场景下的不稳定性，以及 `MockConnector` 的存在，我们**不应该**将其作为推荐的测试工具移动到 SDK 中。它将保留在 E2E 测试目录中（或被逐渐淘汰），作为内部集成测试的实现细节。

以下计划将 `ControllerTestApp` 迁移至 SDK，并更新 harness 引用它。

## [WIP] refactor(testing): Promote ControllerTestApp to SDK and deprecate local harness

### 用户需求
将 `tests/e2e/runtime/harness.py` 中的通用测试组件移动到 `cascade.testing` 模块，以供更广泛使用并减少重复。

### 评论
`ControllerTestApp` 封装了构建 `GlobalConstraint` 和发布消息的逻辑，这对于任何想要测试其应用如何响应控制指令的用户来说都是非常有价值的。将其与 `MockConnector` 结合使用，可以构建出非常健壮的测试。

### 目标
1.  修改 `packages/cascade-sdk/src/cascade/testing.py`，引入 `ControllerTestApp` 类。
2.  修改 `tests/e2e/runtime/harness.py`，改为从 `cascade.testing` 导入该类，保持向后兼容。

### 标签
#intent/refine #flow/ready #priority/medium #comp/sdk #scope/dx #task/domain/testing #task/object/harness #task/action/promote #task/state/continue

---

### Script

#### Acts 1: 将 `ControllerTestApp` 移动到 SDK

我们将在 `testing.py` 中添加必要的导入和类定义。注意我们需要引入 `GlobalConstraint` 和 `asdict`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Awaitable
from unittest.mock import MagicMock
import asyncio

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import (
    Solver,
    Executor,
    ExecutionPlan,
    Connector,
    SubscriptionHandle,
)
from cascade.graph.model import Node, Graph
~~~~~
~~~~~python.new
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Awaitable
from unittest.mock import MagicMock
import asyncio
import uuid
from dataclasses import asdict

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import ( 
    Solver, 
    Executor, 
    ExecutionPlan, 
    Connector, 
    SubscriptionHandle, 
) 
from cascade.graph.model import Node, Graph
from cascade.spec.constraint import GlobalConstraint
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
    def _topic_matches(self, subscription: str, topic: str) -> bool:
        # Simple topic matching for direct match and wildcard at the end
        if subscription == topic:
            return True
        if subscription.endswith("/#"):
            prefix = subscription[:-2]
            if topic.startswith(prefix):
                return True
        return False
~~~~~
~~~~~python.new
    def _topic_matches(self, subscription: str, topic: str) -> bool: 
        # Simple topic matching for direct match and wildcard at the end
        if subscription == topic: 
            return True
        if subscription.endswith("/#"): 
            prefix = subscription[:-2] 
            if topic.startswith(prefix): 
                return True
        return False


class ControllerTestApp:
    """
    A lightweight simulator for the cs-controller CLI tool.
    Useful for testing how a workflow responds to control plane events (pause, resume).
    """

    def __init__(self, connector: Connector):
        self.connector = connector

    async def pause(self, scope: str = "global"):
        constraint = GlobalConstraint(
            id=f"pause-{scope}-{uuid.uuid4().hex[:8]}",
            scope=scope,
            type="pause",
            params={},
        )
        await self._publish(scope, constraint)

    async def resume(self, scope: str = "global"):
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        # Sending an empty dict simulates the connector's behavior for an empty payload
        # (clearing the retained message)
        await self.connector.publish(topic, {}, retain=True)

    async def _publish(self, scope: str, constraint: GlobalConstraint):
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        await self.connector.publish(topic, payload, retain=True)
~~~~~

#### Acts 2: 更新旧 Harness 以重用 SDK 组件

我们将修改 `tests/e2e/runtime/harness.py`，使其仅仅作为 SDK 组件的导入代理，同时保留 `InProcessConnector` 的定义（因为它是一个具体实现，不适合放入通用的 testing 模块）。

~~~~~act
write_file
tests/e2e/runtime/harness.py
~~~~~
~~~~~python
from cascade.connectors.local import LocalBusConnector
# Re-export ControllerTestApp from the official SDK testing module
from cascade.testing import ControllerTestApp

# Alias for backward compatibility with existing e2e tests
# LocalBusConnector handles its own global state internally. 
InProcessConnector = LocalBusConnector

# ControllerTestApp is now imported from cascade.testing
__all__ = ["InProcessConnector", "ControllerTestApp"]
~~~~~

### 下一步建议
迁移完成后，现有的测试无需修改（因为 harness 重新导出了该类），但新测试应直接使用 `from cascade.testing import ControllerTestApp`。这标志着我们测试工具链标准化的重要一步。
