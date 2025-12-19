好的，我们进入 **里程碑 1.4** 的实现阶段。我们将一次性完成使 `cs.recv` 测试通过所需的所有变更。这涉及到创建新的提供者、修改引擎以暴露其连接器、扩展连接器协议以支持取消订阅，以及更新 `LocalBusConnector` 的实现。

## [WIP] feat(providers): 实现信号原语 cs.recv 及依赖的协议扩展

### 错误分析
无（这是 TDD 的实现阶段）。

### 用户需求
实现 `cs.recv` 原子任务，使其能够挂起工作流、等待外部信号并支持超时。

### 评论
`cs.recv` 的实现触及了 Cascade 架构的多个层面。它要求任务能够与 `Engine` 的核心组件（`Connector`）交互。我们通过“资源注入”这一现有模式优雅地解决了这个问题，即让 `Engine` 将其 `Connector` 注册为一个内部资源。此外，为了防止资源泄漏，我们必须扩展 `Connector` 协议，引入可取消的订阅句柄 (`SubscriptionHandle`)。这是实现健壮、长生命周期 Agent 的关键一步。

### 目标
1.  **创建 `signal.py`**: 实现 `cs.recv` 任务，该任务注入 `_internal_connector` 资源。
2.  **修改 `Engine`**: 让 `Engine` 在运行时将其 `Connector` 注册为名为 `_internal_connector` 的内部资源。
3.  **扩展 `Connector` 协议**: 引入 `SubscriptionHandle` 并修改 `subscribe` 方法以返回该句柄，从而支持取消订阅。
4.  **更新 `LocalBusConnector`**: 实现新的 `SubscriptionHandle` 协议，确保订阅可以被正确清理。
5.  **注册 `RecvProvider`**: 在 `pyproject.toml` 中注册新的提供者。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #comp/interfaces #concept/signal #scope/api #ai/instruct #task/domain/providers #task/object/recv-primitive #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `signal.py` 提供者模块

首先，我们创建 `cs.recv` 的核心实现。它依赖一个尚不存在的 `_internal_connector` 资源和一个可取消的订阅句柄。

~~~~~act
write_file
packages/cascade-py/src/cascade/providers/signal.py
~~~~~
~~~~~python
import asyncio
from typing import Optional, Any

from cascade.spec.task import task
from cascade.spec.resource import inject
from cascade.providers import LazyFactory, Provider
from cascade.interfaces.protocols import Connector


@task(name="recv")
async def _recv_task(
    topic: str,
    timeout: Optional[float] = None,
    # This is a special, undocumented resource provided by the Engine
    connector: Connector = inject("_internal_connector"),
) -> Any:
    """
    Pauses execution until a signal is received on the given topic.
    """
    if connector is None:
        raise RuntimeError(
            "cs.recv cannot be used because no Connector is configured in the Engine."
        )

    future = asyncio.Future()

    async def callback(topic: str, payload: Any):
        # Ensure we only set the result once
        if not future.done():
            future.set_result(payload)

    subscription = await connector.subscribe(topic, callback)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        # Re-raise to allow Cascade's error handling to catch it
        raise asyncio.TimeoutError(f"Timed out waiting for signal on topic '{topic}' after {timeout}s")
    finally:
        # Crucially, unsubscribe to prevent resource leaks
        if subscription and hasattr(subscription, "unsubscribe"):
            await subscription.unsubscribe()


class RecvProvider(Provider):
    name = "recv"

    def create_factory(self) -> LazyFactory:
        return _recv_task

~~~~~

#### Acts 2: 修改 Engine 以提供 Connector 资源

现在，我们让 `Engine` 将其 `Connector` 实例注册为一个内部资源，供 `cs.recv` 注入。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target
            
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                active_resources: Dict[str, Any] = {}

                while True:
~~~~~
~~~~~python
            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target
            
            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.resource import resource
                    @resource(name="_internal_connector", scope="run")
                    def _connector_provider():
                        yield self.connector
                    self.register(_connector_provider)
                
                active_resources: Dict[str, Any] = {}

                while True:
~~~~~

#### Acts 3: 扩展 Connector 协议以支持取消订阅

我们修改 `cascade-interfaces` 中的 `protocols.py`，加入 `SubscriptionHandle` 并更新 `subscribe` 的签名。

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
~~~~~
~~~~~python
class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """
~~~~~
~~~~~python
class SubscriptionHandle(Protocol):
    """
    A handle to an active subscription, allowing it to be cancelled.
    """

    async def unsubscribe(self) -> None:
        """Cancels the subscription."""
        ...


class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """
~~~~~

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        """Subscribes to a topic to receive messages (e.g., control commands)."""
        ...
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle":
        """
        Subscribes to a topic to receive messages (e.g., control commands).
        Returns a handle that can be used to unsubscribe.
        """
        ...
~~~~~

#### Acts 4: 更新 `LocalBusConnector` 以实现新协议

现在我们更新 `LocalBusConnector` 来实现可取消的订阅。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable, Optional
from cascade.interfaces.protocols import Connector
from cascade.common.messaging import bus


class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
~~~~~
~~~~~python
import asyncio
import uuid
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable, Optional
from cascade.interfaces.protocols import Connector, SubscriptionHandle
from cascade.common.messaging import bus


class _LocalSubscriptionHandle(SubscriptionHandle):
    """Implementation of the subscription handle for the LocalBusConnector."""

    def __init__(self, parent: "LocalBusConnector", topic: str, queue: asyncio.Queue, listener_task: asyncio.Task):
        self._parent = parent
        self._topic = topic
        self._queue = queue
        self._listener_task = listener_task

    async def unsubscribe(self) -> None:
        # 1. Cancel the listener task
        self._listener_task.cancel()
        try:
            await self._listener_task
        except asyncio.CancelledError:
            pass

        # 2. Remove the queue from the broker's shared state
        async with self._parent._get_lock():
            if self._topic in self._parent._subscriptions:
                try:
                    self._parent._subscriptions[self._topic].remove(self._queue)
                    if not self._parent._subscriptions[self._topic]:
                        del self._parent._subscriptions[self._topic]
                except ValueError:
                    # Queue already removed, which is fine
                    pass
        
        # 3. Remove task from parent's tracked listeners to prevent memory leak
        try:
            self._parent._listener_tasks.remove(self._listener_task)
        except ValueError:
            pass


class LocalBusConnector(Connector):
    """
    A robust, in-memory implementation of the Connector protocol.
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._is_connected:
            return

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            # This ensures that when subscribe() returns, all existing 
            # state (constraints, etc.) has been processed by the engine.
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error("localbus.retained_callback_error", topic=retained_topic, error=e)

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)
~~~~~
~~~~~python
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        queue = asyncio.Queue()
        
        async with self._get_lock():
            self._subscriptions[topic].append(queue)

            # Deliver Retained Messages Synchronously for the caller.
            for retained_topic, payload in self._retained_messages.items():
                if self._topic_matches(topic, retained_topic):
                    try:
                        await callback(retained_topic, payload)
                    except Exception as e:
                        bus.error("localbus.retained_callback_error", topic=retained_topic, error=e)

        # Start a background listener for NEW incoming messages
        task = asyncio.create_task(self._listener_loop(queue, callback))
        self._listener_tasks.append(task)
        
        return _LocalSubscriptionHandle(self, topic, queue, task)
~~~~~

#### Acts 5: 注册 `cs.recv` 提供者

最后，我们将新的提供者注册到 `cascade-py` 的入口点。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~python
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
wait = "cascade.providers.time:TimeWaitProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
~~~~~
~~~~~python
[project.entry-points."cascade.providers"]
shell = "cascade.providers.shell:ShellProvider"
wait = "cascade.providers.time:TimeWaitProvider"
recv = "cascade.providers.signal:RecvProvider"
template = "cascade.providers.template:TemplateProvider"
"http.get" = "cascade.providers.http:HttpGetProvider"
~~~~~

### 下一步建议
运行测试。所有与 `cs.recv` 相关的测试现在都应该通过了。确认通过后，我将为这个重要的里程碑创建一个 `[COMMIT]` 计划。
