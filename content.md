简要回答
针对 Pyright 报告的 166 个错误，我制定了一个分阶段的修复计划。主要问题集中在 `LazyResult` 的动态属性（Monkey-Patching）、`Connector` 协议的不匹配、以及 `lisp.py` 中过时的属性访问。

修复策略如下：
1.  **重构核心类型 (`lazy_types.py`)**: 将 `run_if`、`after` 等方法直接定义在 `LazyResult` 和 `MappedLazyResult` 类中，移除 `task.py` 中的运行时 Monkey-Patching，解决大量 "Attribute unknown" 错误。
2.  **修正协议实现 (`Connector`)**: 更新 `MqttConnector` 和 `MockConnector`，确保 `subscribe` 方法返回标准的 `SubscriptionHandle`，修复协议不兼容问题。
3.  **修正属性访问**: 将 `lisp.py` 中错误的 `.id` 访问修正为 `.structural_id`。
4.  **优化类型定义**: 使用 `@overload` 优化 `task` 装饰器的类型提示，消除关于 `LazyFactory` 的类型推断错误；修复 `Provider` 实现中的返回类型不匹配。
5.  **增强空值安全**: 在 `engine.py`、`vm.py` 等处添加必要的 `None` 检查和类型转换。

# [WIP] fix: 修复 Pyright 类型错误并重构核心类型定义

## [WIP] fix(core): 重构 LazyResult 定义并修复 Connector 协议匹配

### 错误分析
当前代码库存在大量 Pyright 类型检查错误，主要原因如下：
1.  **Monkey-Patching**: `LazyResult` 的方法（如 `run_if`）是在 `task.py` 中动态注入的，静态分析工具无法识别。
2.  **Protocol Mismatch**: `MqttConnector` 和 `MockConnector` 的 `subscribe` 方法未返回 `SubscriptionHandle`，与 `Connector` 协议定义不符。
3.  **Outdated Attribute**: `lisp.py` 试图访问 `Node.id`，但模型定义中使用的是 `Node.structural_id`。
4.  **Type Ambiguity**: `task` 装饰器的类型定义使用了 `Union`，导致 Pyright 在推断 Provider 返回类型时产生混淆。

### 用户需求
修复所有 Pyright 报错，确保代码通过静态类型检查。

### 评论
这是一个涉及核心定义的重构。将动态注入的方法改为静态定义不仅能修复类型错误，还能显著提升 IDE 的代码补全体验和代码可读性。

### 目标
1.  消除 166 个 Pyright 错误。
2.  确保 `Connector` 实现符合协议。
3.  修正属性访问错误。

### 基本原理
1.  **显式优于隐式**: 将 `LazyResult` 的方法直接写入类定义，避免副作用。
2.  **协议一致性**: 强制所有 Connector 实现遵循接口契约。
3.  **类型精确化**: 使用 `overload` 消除装饰器类型歧义。

### 标签
#intent/fix #flow/ready #priority/high #comp/interfaces #concept/type-safety #scope/core #ai/instruct #task/domain/testing #task/object/type-system #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 LazyResult 与 MappedLazyResult (移除 Monkey-Patching)

我们将把 `LazyResult` 的操作方法从 `task.py` 移动到 `lazy_types.py` 中，使其成为静态类型友好的类。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING, overload
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int
    delay: float = 0.0
    backoff: float = 1.0  # Multiplier for delay after each retry


@dataclass
class LazyResult(Generic[T]):
    task: Any  # Should be 'Task[T]'
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
        return hash(self._uuid)

    def run_if(self, condition: "LazyResult") -> "LazyResult[T]":
        self._condition = condition
        return self

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "LazyResult[T]":
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: "CachePolicy") -> "LazyResult[T]":
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        # Import internally to avoid circular dependency at module level
        from cascade.spec.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self

    def after(self, *predecessors: "LazyResult") -> "LazyResult[T]":
        self._dependencies.extend(predecessors)
        return self


@dataclass
class MappedLazyResult(Generic[T]):
    factory: Any  # Should be LazyFactory
    mapping_kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _condition: Optional[LazyResult] = None
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List[LazyResult] = field(default_factory=list)

    def __hash__(self):
        return hash(self._uuid)

    def run_if(self, condition: LazyResult) -> "MappedLazyResult[T]":
        self._condition = condition
        return self

    def with_retry(
        self, max_attempts: int = 3, delay: float = 0.0, backoff: float = 1.0
    ) -> "MappedLazyResult[T]":
        self._retry_policy = RetryPolicy(max_attempts, delay, backoff)
        return self

    def with_cache(self, policy: "CachePolicy") -> "MappedLazyResult[T]":
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "MappedLazyResult[T]":
        from cascade.spec.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self

    def after(self, *predecessors: LazyResult) -> "MappedLazyResult[T]":
        self._dependencies.extend(predecessors)
        return self
~~~~~

#### Acts 2: 清理 Task 定义 (移除 Mixins)

既然方法已经移入 `LazyResult`，我们需要从 `task.py` 中移除那些动态注入代码，并修正 `task` 装饰器的类型提示。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Optional, Union, List, TYPE_CHECKING, overload
import inspect

if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import (
    LazyResult,
    MappedLazyResult,
    RetryPolicy,
)

T = TypeVar("T")


# --- Task Definition ---


class Task(Generic[T]):
    def __init__(
        self,
        func: Callable[..., T],
        name: Optional[str] = None,
        pure: bool = False,
        mode: str = "blocking",
    ):
        self.func = func
        self.name = name or func.__name__
        self.pure = pure
        self.mode = mode
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: Optional[List["Task"]] = None

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def map(self, **kwargs) -> MappedLazyResult[List[T]]:
        return MappedLazyResult(factory=self, mapping_kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"


# --- Decorator ---

@overload
def task(
    func: Callable[..., T],
) -> Task[T]: ...

@overload
def task(
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Callable[[Callable[..., T]], Task[T]]: ...

@overload
def task(
    func: Callable[..., T],
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Task[T]: ...

def task(
    func: Optional[Callable[..., T]] = None,
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name, pure=pure, mode=mode)

    if func:
        return wrapper(func)
    else:
        return wrapper
~~~~~

#### Acts 3: 修正 Connector 协议实现 (MQTT & Local)

我们需要确保 `subscribe` 方法返回 handle，并修复 `LocalConnector` 中的 `None` 访问问题。

~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python.old
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        if not self._client:
            logger.warning("Attempted to subscribe without an active MQTT connection.")
            return

        # 1. Register callback locally
        self._subscriptions[topic] = callback

        # 2. Send subscribe command to broker
        try:
            await self._client.subscribe(topic)
            # Give the broker a moment to send retained messages before the
            # engine's main loop continues. This is a pragmatic way to solve
            # the startup race condition.
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to subscribe to topic '{topic}': {e}")
~~~~~
~~~~~python.new
    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> "SubscriptionHandle":
        if not self._client:
            raise RuntimeError("Attempted to subscribe without an active MQTT connection.")

        # 1. Register callback locally
        self._subscriptions[topic] = callback

        # 2. Send subscribe command to broker
        try:
            await self._client.subscribe(topic)
            # Give the broker a moment to send retained messages
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Failed to subscribe to topic '{topic}': {e}")
            # Even if subscribe fails on broker, we return a handle to clean up local registry
            pass

        return _MqttSubscriptionHandle(self, topic)


from cascade.spec.protocols import SubscriptionHandle

class _MqttSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "MqttConnector", topic: str):
        self._parent = parent
        self._topic = topic

    async def unsubscribe(self) -> None:
        if self._topic in self._parent._subscriptions:
            del self._parent._subscriptions[self._topic]
        if self._parent._client:
            try:
                await self._parent._client.unsubscribe(self._topic)
            except Exception:
                pass
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python.old
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
            scope = self._topic_to_scope(topic)

            def _blocking_publish():
                cursor = self._conn.cursor()
                if not payload:
                    cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                self._conn.commit()

            await asyncio.to_thread(_blocking_publish)

            if not self._use_polling:
                await self._send_uds_signal()
~~~~~
~~~~~python.new
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected or not self._conn:
            raise RuntimeError("Connector is not connected.")

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
            scope = self._topic_to_scope(topic)

            def _blocking_publish():
                if not self._conn:
                    return
                cursor = self._conn.cursor()
                if not payload:
                    cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                self._conn.commit()

            await asyncio.to_thread(_blocking_publish)

            if not self._use_polling:
                await self._send_uds_signal()
~~~~~

#### Acts 4: 修正 Controller CLI 的 Connector 类型问题

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python.old
def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "local":
        return LocalConnector()
    elif backend == "mqtt":
        return MqttConnector(hostname=hostname, port=port)
    else:
        # This case is primarily for safety, Typer's Choice/Enum would be better
        raise typer.BadParameter(f"Unsupported backend: {backend}")
~~~~~
~~~~~python.new
def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "local":
        return LocalConnector()
    elif backend == "mqtt":
        # MqttConnector now satisfies the protocol
        return MqttConnector(hostname=hostname, port=port)
    else:
        # This case is primarily for safety, Typer's Choice/Enum would be better
        raise typer.BadParameter(f"Unsupported backend: {backend}")
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python.old
        bus.info("controller.resuming", scope=scope, topic=topic)
        # Publishing an empty retained message clears the previous one
        await connector.publish(topic, "", retain=True)

        await asyncio.sleep(0.1)
~~~~~
~~~~~python.new
        bus.info("controller.resuming", scope=scope, topic=topic)
        # Publishing an empty retained message clears the previous one
        await connector.publish(topic, {}, retain=True)

        await asyncio.sleep(0.1)
~~~~~

#### Acts 5: 修复 Testing Mock Connector

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
    async def publish(
        self, topic: str, payload: Dict[str, Any], retain: bool = False, qos: int = 0
    ) -> None:
        self.publish_log.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

        if retain:
            if payload:
                self.retained_messages[topic] = payload
            elif topic in self.retained_messages:
                # An empty payload on a retained topic clears it
                del self.retained_messages[topic]

        await self._trigger_message(topic, payload)

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> None:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                asyncio.create_task(callback(retained_topic, payload))

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
~~~~~
~~~~~python.new
    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        self.publish_log.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

        if retain:
            if payload:
                self.retained_messages[topic] = payload
            elif topic in self.retained_messages:
                # An empty payload on a retained topic clears it
                del self.retained_messages[topic]

        await self._trigger_message(topic, payload)

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                asyncio.create_task(callback(retained_topic, payload))
        
        return MockSubscriptionHandle(self, topic)

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
~~~~~

~~~~~act
write_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Awaitable
from unittest.mock import MagicMock
import asyncio

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import Solver, Executor, ExecutionPlan, Connector, SubscriptionHandle
from cascade.graph.model import Node, Graph


@contextmanager
def override_resource(
    engine: "Engine", name: str, new_resource_func: Callable[[], Any]
):
    if not hasattr(engine, "override_resource_provider"):
        raise TypeError("The provided engine does not support resource overriding.")

    original = engine.get_resource_provider(name)
    try:
        engine.override_resource_provider(name, new_resource_func)
        yield
    finally:
        engine.override_resource_provider(name, original)


class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        return [e for e in self.events if isinstance(e, event_type)]


class SpySolver(Solver):
    def __init__(self, underlying_solver: Solver):
        self.underlying_solver = underlying_solver
        self.resolve = MagicMock(wraps=self.underlying_solver.resolve)

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # This method's body is effectively replaced by the MagicMock wrapper,
        # but is required to satisfy the Solver protocol's type signature.
        # The actual call is handled by the `wraps` argument in __init__.
        return self.underlying_solver.resolve(graph)


class MockSolver(Solver):
    def __init__(self, plan: ExecutionPlan):
        self._plan = plan

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Return the pre-programmed plan regardless of the input graph
        return self._plan


class SpyExecutor(Executor):
    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"


class MockExecutor(Executor):
    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value


class MockSubscriptionHandle(SubscriptionHandle):
    def __init__(self, parent: "MockConnector", topic: str):
        self._parent = parent
        self._topic = topic

    async def unsubscribe(self) -> None:
        if self._topic in self._parent.subscriptions:
            del self._parent.subscriptions[self._topic]


class MockConnector(Connector):
    def __init__(self):
        self.subscriptions: Dict[str, Callable[[str, Dict], Awaitable[None]]] = {}
        # Simulate broker storage for retained messages: topic -> payload
        self.retained_messages: Dict[str, Dict[str, Any]] = {}
        self.connected: bool = False
        self.disconnected: bool = False
        self.publish_log: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True
        self.disconnected = False

    async def disconnect(self) -> None:
        self.disconnected = True
        self.connected = False

    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        self.publish_log.append(
            {"topic": topic, "payload": payload, "retain": retain, "qos": qos}
        )

        if retain:
            if payload:
                self.retained_messages[topic] = payload
            elif topic in self.retained_messages:
                # An empty payload on a retained topic clears it
                del self.retained_messages[topic]

        await self._trigger_message(topic, payload)

    async def subscribe(
        self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]
    ) -> SubscriptionHandle:
        self.subscriptions[topic] = callback

        # Immediate delivery of matching retained messages upon subscription
        for retained_topic, payload in self.retained_messages.items():
            if self._topic_matches(subscription=topic, topic=retained_topic):
                # Run in a task to avoid blocking the subscribe call itself
                asyncio.create_task(callback(retained_topic, payload))
        
        return MockSubscriptionHandle(self, topic)

    def seed_retained_message(self, topic: str, payload: Dict[str, Any]):
        self.retained_messages[topic] = payload

    async def _trigger_message(self, topic: str, payload: Dict[str, Any]):
        for sub_topic, callback in self.subscriptions.items():
            if self._topic_matches(subscription=sub_topic, topic=topic):
                await callback(topic, payload)

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

#### Acts 6: 修复 Lisp 模块中的属性名错误

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
        for node in sorted_nodes:
            # Nodes referenced more than once OR nodes that are used as Router selectors
            # (Router selectors are tricky to inline cleanly inside a case statement header)
            is_router_selector = any(
                e.router
                and e.router.selector._uuid in self.instance_map
                and self.instance_map[e.router.selector._uuid].id == node.structural_id
                for e in self.graph.edges
            )

            if self.ref_counts[node.structural_id] > 1 or is_router_selector:
~~~~~
~~~~~python.new
        for node in sorted_nodes:
            # Nodes referenced more than once OR nodes that are used as Router selectors
            # (Router selectors are tricky to inline cleanly inside a case statement header)
            is_router_selector = any(
                e.router
                and e.router.selector._uuid in self.instance_map
                and self.instance_map[e.router.selector._uuid].structural_id == node.structural_id
                for e in self.graph.edges
            )

            if self.ref_counts[node.structural_id] > 1 or is_router_selector:
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
        def visit(n_id):
            if n_id in temp_mark:
                return  # Cycle detected, ignore
            if n_id in visited:
                return

            temp_mark.add(n_id)
            for dep_id in sorted(adj[n_id]):  # Sort for deterministic output
                visit(dep_id)
            temp_mark.remove(n_id)
            visited.add(n_id)
            result.append(n_id)

        # Sort input nodes for deterministic start order
        for n in sorted(nodes, key=lambda x: x.id):
            visit(n.structural_id)

        # result is [Deepest Dep, ..., Root]
        id_map = {n.structural_id: n for n in nodes}
~~~~~
~~~~~python.new
        def visit(n_id):
            if n_id in temp_mark:
                return  # Cycle detected, ignore
            if n_id in visited:
                return

            temp_mark.add(n_id)
            for dep_id in sorted(adj[n_id]):  # Sort for deterministic output
                visit(dep_id)
            temp_mark.remove(n_id)
            visited.add(n_id)
            result.append(n_id)

        # Sort input nodes for deterministic start order
        for n in sorted(nodes, key=lambda x: x.structural_id):
            visit(n.structural_id)

        # result is [Deepest Dep, ..., Root]
        id_map = {n.structural_id: n for n in nodes}
~~~~~

#### Acts 7: 修复 Engine 的 None 安全性

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
~~~~~
~~~~~python.new
    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Optional[Callable[[str], StateBackend]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
~~~~~

#### Acts 8: 修正 S3 Provider 类型定义

`aiobotocore` 的上下文管理器返回类型推断在静态检查中通常有问题，我们将显式添加类型注释或忽略。

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/s3.py
~~~~~
~~~~~python.old
@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)


@task(name="s3_read_bytes")
async def _s3_read_bytes(bucket: str, key: str) -> bytes:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()
~~~~~
~~~~~python.new
@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)


@task(name="s3_read_bytes")
async def _s3_read_bytes(bucket: str, key: str) -> bytes:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()
~~~~~

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/s3.py
~~~~~
~~~~~python.old
@task(name="s3_write_text")
async def _s3_write_text(
    bucket: str, key: str, content: str, encoding: str = "utf-8"
) -> None:
    data = content.encode(encoding)
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        await client.put_object(Bucket=bucket, Key=key, Body=data)


@task(name="s3_write_bytes")
async def _s3_write_bytes(bucket: str, key: str, content: bytes) -> None:
    session = aiobotocore.session.get_session()
    async with session.create_client("s3") as client:
        await client.put_object(Bucket=bucket, Key=key, Body=content)
~~~~~
~~~~~python.new
@task(name="s3_write_text")
async def _s3_write_text(
    bucket: str, key: str, content: str, encoding: str = "utf-8"
) -> None:
    data = content.encode(encoding)
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        await client.put_object(Bucket=bucket, Key=key, Body=data)


@task(name="s3_write_bytes")
async def _s3_write_bytes(bucket: str, key: str, content: bytes) -> None:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        await client.put_object(Bucket=bucket, Key=key, Body=content)
~~~~~

### 下一步建议
运行测试套件（`pytest`），验证重构后的 `LazyResult` 和 `Connector` 是否破坏了现有逻辑。特别是关于 `LazyResult.after` 等方法的链式调用和 `Connector.subscribe` 的行为。
