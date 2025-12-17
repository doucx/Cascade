好的，我们正式启动路线图的第二阶段：遥测系统实现。

此阶段的核心目标是为 Cascade 建立“感知”能力，使其能够向外部世界广播其内部状态。我们将严格遵循“协议优先”和“零强制依赖”的原则，首先定义接口和数据结构，并将连接器作为可选组件集成到引擎中。

我将生成一个计划来执行此阶段的第一部分：定义协议、数据模型，并为连接器在引擎中植入生命周期挂钩。

## [WIP] feat: 定义遥测协议并集成连接器挂钩

### 用户需求
开始执行“Cascade 架构演进技术路线图 (v2.0)”中的第二阶段：遥测系统实现。

### 评论
这是 Cascade 从一个本地库演变为一个可观测、可管理的分布式系统的关键一步。建立遥测系统是实现“向下因果”（通过环境参数调节微观行为）和“系统园丁”模式的基础。此计划奠定了整个遥测架构的基石。

### 目标
1.  在 `cascade.runtime.protocols` 中定义 `Connector` 协议，作为系统与外部世界I/O的唯一契约。
2.  在 `cascade.spec` 中定义遥测事件的标准化数据模型（Schema）。
3.  修改 `Engine` 的构造函数和 `run` 方法，使其能够接纳一个可选的 `Connector` 实例，并管理其 `connect`/`disconnect` 生命周期。
4.  创建一个新的 `TelemetrySubscriber`，它将监听内部的 `MessageBus` 事件，并将其转换为遥测事件通过 `Connector` 发送出去。
5.  更新顶层的 `cs.run` 函数，使其能够实例化并连接 `TelemetrySubscriber`。

### 基本原理
我们严格遵循“协议即契约”和“渐进增强”的设计原则。
1.  **协议优先**: 首先定义 `Connector` 协议，确保 `Engine` 仅依赖于抽象接口，而非任何具体的实现（如 MQTT）。这使得未来可以轻松支持 Kafka、HTTP Webhooks 等其他通信方式。
2.  **关注点分离**: 通过创建一个专门的 `TelemetrySubscriber`，我们将“遥测事件转换与发布”的逻辑与 `Engine` 的核心“工作流执行”逻辑完全解耦。`Engine` 只负责执行和发布内部事件，而 `TelemetrySubscriber` 负责监听这些内部事件并与外部世界对话。
3.  **零强制依赖**: 具体的 `MqttConnector` 将在未来的独立包中实现。本次修改只涉及核心库，不引入任何新的重量级依赖，确保 Cascade 的核心保持轻量。

### 标签
#intent/architect #intent/build #flow/ready #priority/high
#comp/runtime #concept/telemetry #scope/api #scope/core
#ai/instruct
#task/domain/runtime #task/object/telemetry #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 在 `protocols.py` 中定义 `Connector` 协议

我们首先修改 `cascade.runtime.protocols`，加入 `Connector` 协议的定义，这是所有遥测交互的基础。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict, Optional
from cascade.graph.model import Graph, Node
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable
from cascade.graph.model import Graph, Node
~~~~~
~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """

    def map(self, **kwargs) -> Any:
        """
        Creates a mapped lazy result by applying this factory over iterables.
        """
        ...
~~~~~
~~~~~python
class LazyFactory(Protocol):
    """
    Protocol for any object that can produce a MappedLazyResult via a .map() method.
    Example: Task, ShellTask, etc.
    """

    def map(self, **kwargs) -> Any:
        """
        Creates a mapped lazy result by applying this factory over iterables.
        """
        ...


class Connector(Protocol):
    """
    Protocol for a connector that bridges the Cascade runtime with the outside world.
    It's responsible for all non-business-logic I/O, primarily for telemetry and control.
    """

    async def connect(self) -> None:
        """Establishes a connection to the external system (e.g., MQTT Broker)."""
        ...

    async def disconnect(self) -> None:
        """Disconnects from the external system and cleans up resources."""
        ...

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """Publishes a message (e.g., a telemetry event) to a specific topic."""
        ...

    async def subscribe(self, topic: str, callback: Callable[[str, Dict], Awaitable[None]]) -> None:
        """Subscribes to a topic to receive messages (e.g., control commands)."""
        ...
~~~~~

#### Acts 2: 创建遥测数据模型

接下来，我们创建一个新文件 `src/cascade/spec/telemetry.py` 来定义标准化的遥测事件数据结构。

~~~~~act
write_file
src/cascade/spec/telemetry.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass(frozen=True)
class TelemetryHeader:
    """Standard header for all telemetry messages."""
    v: str = "1.0"
    ts: str = "" # ISO 8601 UTC timestamp
    run_id: str = ""
    org_id: str = "local"
    project_id: str = "default"
    source: str = "" # e.g., "worker-hostname-pid"


@dataclass(frozen=True)
class LifecycleEvent:
    """Represents engine lifecycle events."""
    event: str # "ENGINE_STARTED", "ENGINE_STOPPED"


@dataclass(frozen=True)
class TaskStateEvent:
    """Represents a change in a task's execution state."""
    task_id: str
    task_name: str
    state: str # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    duration_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceEvent:
    """Represents an event related to a resource's lifecycle."""
    resource_name: str
    action: str # ACQUIRE | RELEASE
    current_usage: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 3: 扩展 `Engine` 以支持 `Connector`

现在修改 `Engine` 类，使其能够接收 `Connector` 实例，并管理其生命周期。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.runtime.protocols import Solver, Executor, StateBackend
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~
~~~~~python
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
from cascade.runtime.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
~~~~~
~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~python
class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )
        
        state_backend = self.state_backend_cls(run_id=run_id)

        with ExitStack() as stack:
            try:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

                duration = time.time() - start_time
                self.bus.publish(
                    RunFinished(run_id=run_id, status="Succeeded", duration=duration)
                )
                return final_result

            except Exception as e:
                duration = time.time() - start_time
                self.bus.publish(
                    RunFinished(
                        run_id=run_id,
                        status="Failed",
                        duration=duration,
                        error=f"{type(e).__name__}: {e}",
                    )
                )
                raise
~~~~~
~~~~~python
        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )
        
        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            if self.connector:
                await self.connector.connect()

            with ExitStack() as stack:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            if self.connector:
                await self.connector.disconnect()
~~~~~

#### Acts 4: 创建 `TelemetrySubscriber` 并更新顶层 `run` 函数

现在我们创建 `TelemetrySubscriber`，它将作为内部事件和外部遥测之间的桥梁。同时，我们将更新 `cs.run` 函数来启用它。

~~~~~act
write_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
import platform
import os
import time
from datetime import datetime, timezone
from .bus import MessageBus
from ..messaging.bus import bus as messaging_bus
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    Event,
    ResourceAcquired,
    ResourceReleased,
)
from ..spec.telemetry import TelemetryHeader, LifecycleEvent, TaskStateEvent
from .protocols import Connector


class HumanReadableLogSubscriber:
    """
    Listens to runtime events and translates them into semantic messages
    on the messaging bus. It acts as a bridge between the event domain
    and the user-facing message domain.
    """

    def __init__(self, event_bus: MessageBus):
        # Subscribe to relevant events from the core event_bus
        event_bus.subscribe(RunStarted, self.on_run_started)
        event_bus.subscribe(RunFinished, self.on_run_finished)
        event_bus.subscribe(TaskExecutionStarted, self.on_task_started)
        event_bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        event_bus.subscribe(TaskSkipped, self.on_task_skipped)
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)

    def on_run_started(self, event: RunStarted):
        messaging_bus.info("run.started", target_tasks=event.target_tasks)
        if event.params:
            messaging_bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            messaging_bus.info("run.finished_success", duration=event.duration)
        else:
            messaging_bus.error("run.finished_failure", duration=event.duration, error=event.error)

    def on_task_started(self, event: TaskExecutionStarted):
        messaging_bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            messaging_bus.info("task.finished_success", task_name=event.task_name, duration=event.duration)
        else:
            messaging_bus.error("task.finished_failure", task_name=event.task_name, duration=event.duration, error=event.error)

    def on_task_skipped(self, event: TaskSkipped):
        messaging_bus.info("task.skipped", task_name=event.task_name, reason=event.reason)

    def on_task_retrying(self, event: TaskRetrying):
        messaging_bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error
        )


class TelemetrySubscriber:
    """
    Listens to runtime events and publishes them as structured telemetry
    data via a Connector.
    """
    def __init__(self, event_bus: MessageBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
        event_bus.subscribe(Event, self.on_event)

    def _create_header(self, run_id: str) -> dict:
        return {
            "v": "1.0",
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "org_id": os.getenv("CASCADE_ORG_ID", "local"),
            "project_id": os.getenv("CASCADE_PROJECT_ID", "default"),
            "source": self._source_id,
        }

    async def on_event(self, event: Event):
        if not event.run_id:
            return

        payload = self._create_header(event.run_id)
        topic = f"cascade/telemetry/{payload['org_id']}/{payload['project_id']}/{event.run_id}/events"
        
        event_body = {}
        if isinstance(event, (TaskExecutionStarted, TaskExecutionFinished, TaskSkipped)):
            state_map = {
                TaskExecutionStarted: "RUNNING",
                TaskExecutionFinished: "COMPLETED" if event.status == "Succeeded" else "FAILED",
                TaskSkipped: "SKIPPED",
            }
            event_body = {
                "type": "TaskStateEvent",
                "task_id": event.task_id,
                "task_name": event.task_name,
                "state": state_map[type(event)],
                "duration_ms": getattr(event, 'duration', 0) * 1000,
                "error": getattr(event, 'error', None) or "",
            }

        elif isinstance(event, RunStarted):
             event_body = {"type": "LifecycleEvent", "event": "ENGINE_STARTED"}
        
        elif isinstance(event, RunFinished):
             event_body = {"type": "LifecycleEvent", "event": "ENGINE_STOPPED"}
        
        # We can add more event types like ResourceEvent later

        if event_body:
            payload["body"] = event_body
            # Fire-and-forget publish
            asyncio.create_task(self._connector.publish(topic, payload))
~~~~~
~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .runtime.exceptions import DependencyMissingError
from .adapters.solvers.native import NativeSolver
from .adapters.executors.local import LocalExecutor
~~~~~
~~~~~python
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from .runtime.exceptions import DependencyMissingError
from .runtime.protocols import Connector
from .adapters.solvers.native import NativeSolver
from .adapters.executors.local import LocalExecutor
~~~~~
~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~
~~~~~python
def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)

    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the human-readable log translator
    HumanReadableLogSubscriber(event_bus)
    # Attach the telemetry publisher if a connector is provided
    if connector:
        TelemetrySubscriber(event_bus, connector)

    # 3. Assemble the default Engine
    solver = NativeSolver()
    executor = LocalExecutor()

    engine = Engine(
        solver=solver,
        executor=executor,
        bus=event_bus,
        system_resources=system_resources,
        connector=connector,
    )

    return asyncio.run(engine.run(target, params=params))
~~~~~

### 下一步建议
我们已经成功地为遥测系统建立了核心协议和集成点。现在，核心库已经“遥测就绪”。

下一步是实现一个具体的 `Connector`。根据路线图，我建议：
1.  创建一个新的、独立的 Python 包（例如 `cascade-connectors-mqtt`）。
2.  在该包中实现 `MqttConnector`，它将依赖 `aiomqtt` 并实现我们刚刚定义的 `Connector` 协议。
3.  编写集成测试，使用一个 Mock 的 MQTT Broker 来验证 `Engine` 在运行时能够通过 `MqttConnector` 正确地发布遥测事件。

如果你同意，我将准备开始实施 `MqttConnector`。
