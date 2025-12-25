## [WIP] feat(arch): 迁移核心执行逻辑至 CascadeApp

### 用户需求
执行 ADR-013 阶段二：将 `cs.run` 中的核心执行逻辑（Engine 实例化、基础设施配置等）迁移并封装到 `CascadeApp` 类中。

### 评论
为了打破潜在的循环依赖（`sdk` <-> `application`），我们将采取“代码复制与解耦”的策略。我们将把 `_internal_gather` 和 `_create_state_backend_factory` 等辅助逻辑直接实现在 `CascadeApp` 模块内部（或作为私有辅助函数），而不是从 `sdk` 导入。同时，我们将从 `cascade-application` 的依赖列表中移除 `cascade-sdk`。这将使 `CascadeApp` 成为一个独立的、底层的执行协调器，为后续 `sdk` 层对其的引用扫清障碍。

### 目标
1.  修改 `packages/cascade-application/pyproject.toml`，移除对 `cascade-sdk` 的依赖。
2.  在 `packages/cascade-application/src/cascade/app/__init__.py` 中完整实现 `CascadeApp` 类：
    *   实现 `__init__`：处理配置、初始化 `Engine`、`MessageBus`、`Renderer` 和 `Subscribers`。
    *   实现 `run`：调用 `engine.run`。
    *   实现辅助逻辑：`_internal_gather` (作为本地 Task) 和 `state_backend_factory` 创建逻辑。

### 基本原理
通过在 `CascadeApp` 中独立实现所有必要的辅助逻辑，我们消除了对 `cascade-sdk` 的运行时依赖。这不仅解决了循环依赖问题，也使得 `Application` 层更加自包含和健壮。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/engine #concept/architecture #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-app #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 调整依赖关系

首先，我们从 `cascade-application` 的构建配置中移除 `cascade-sdk`，这是打破循环依赖的关键一步。

~~~~~act
patch_file
packages/cascade-application/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-graph",
  "cascade-sdk"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-engine",
  "cascade-graph",
  "cascade-common"
]
~~~~~

#### Acts 2: 实现 CascadeApp

现在，我们在 `packages/cascade-application/src/cascade/app/__init__.py` 中实现完整的 `CascadeApp` 逻辑。我们将引入所有必要的底层组件，并重新实现 `_internal_gather` 和状态后端工厂逻辑。

~~~~~act
write_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, List, Tuple, Union, Optional, Callable

from cascade.spec.lazy_types import LazyResult
from cascade.spec.task import task
from cascade.spec.protocols import Connector, StateBackend

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers (Duplicated from sdk to avoid circular dependency) ---

@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """An internal pure task used to gather results from a list."""
    return list(args)


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
) -> Optional[Callable[[str], StateBackend]]:
    """
    Helper to create a factory function from a backend specification (URI or object).
    """
    if backend_spec is None:
        return None  # Engine defaults to InMemory

    if callable(backend_spec):
        return backend_spec

    if isinstance(backend_spec, str):
        if backend_spec.startswith("redis://"):
            try:
                import redis
                from cascade.adapters.state.redis import RedisStateBackend
            except ImportError:
                raise ImportError(
                    "The 'redis' library is required for redis:// backends."
                )

            # Create a shared client pool
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


# --- CascadeApp ---

class CascadeApp:
    """
    The central manager for a workflow's lifecycle, encapsulating all
    infrastructure, configuration, and top-level operations.
    """

    def __init__(
        self,
        target: Union[LazyResult, List[Any], Tuple[Any, ...]],
        params: Optional[Dict[str, Any]] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        log_level: str = "INFO",
        log_format: str = "human",
        connector: Optional[Connector] = None,
        state_backend: Union[str, Callable[[str], StateBackend], None] = None,
    ):
        """
        Initializes the application context.

        Args:
            target: The workflow target (LazyResult, list, or tuple).
            params: Parameters to pass to the workflow.
            system_resources: System-wide resources capacity (e.g. {"gpu": 1}).
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
            log_format: Logging format ("human" or "json").
            connector: Optional external connector (e.g. MQTT).
            state_backend: State persistence backend URI or factory.
        """
        self.raw_target = target
        self.params = params
        self.system_resources = system_resources
        self.connector = connector

        # 1. Handle Auto-Gathering
        if isinstance(target, (list, tuple)):
            if not target:
                self.workflow_target = _internal_gather()  # Empty gather
            else:
                self.workflow_target = _internal_gather(*target)
        else:
            self.workflow_target = target

        # 2. Setup Messaging & Rendering
        if log_format == "json":
            self.renderer = JsonRenderer(min_level=log_level)
        else:
            self.renderer = CliRenderer(store=bus.store, min_level=log_level)
        
        # Inject renderer into the GLOBAL bus (as per current architecture)
        # TODO: In future, we might want scoped buses per App instance.
        bus.set_renderer(self.renderer)

        # 3. Setup Event System
        self.event_bus = MessageBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
        
        self.telemetry_subscriber = None
        if self.connector:
            self.telemetry_subscriber = TelemetrySubscriber(self.event_bus, self.connector)

        # 4. Setup Engine Components
        self.solver = NativeSolver()
        self.executor = LocalExecutor()
        self.sb_factory = _create_state_backend_factory(state_backend)

        # 5. Create Engine
        self.engine = Engine(
            solver=self.solver,
            executor=self.executor,
            bus=self.event_bus,
            system_resources=self.system_resources,
            connector=self.connector,
            state_backend_factory=self.sb_factory,
        )

        # Register managed subscribers for graceful shutdown
        # (Engine handles this via add_subscriber, but currently Engine implementation 
        #  of add_subscriber expects objects with 'shutdown' method. 
        #  TelemetrySubscriber has it. HumanReadableLogSubscriber does not.)
        if self.telemetry_subscriber:
            self.engine.add_subscriber(self.telemetry_subscriber)

    def run(self) -> Any:
        """
        Executes the workflow and returns the final result.
        """
        return asyncio.run(
            self.engine.run(self.workflow_target, params=self.params)
        )

    def visualize(self) -> str:
        """Generates and returns a Graphviz DOT string of the workflow."""
        # TODO: Implement in Stage 3
        raise NotImplementedError("visualize() is not yet implemented in CascadeApp")

    def dry_run(self) -> None:
        """Builds and prints the execution plan without running any tasks."""
        # TODO: Implement in Stage 3
        raise NotImplementedError("dry_run() is not yet implemented in CascadeApp")
~~~~~

### 下一步建议
阶段二已完成。`CascadeApp` 现在拥有了完整的初始化和运行逻辑，并且没有引入不必要的依赖。

接下来的**阶段三**是统一所有入口点。我们需要实现 `visualize` 和 `dry_run` 方法。这意味着我们需要将 `cascade-sdk` 中 `visualize` 和 `dry_run` 的逻辑（主要是图构建和分析部分）迁移到 `CascadeApp` 中。由于这涉及到 `cascade-graph` 和 `cascade-sdk.tools` 中的一些逻辑，我们需要小心处理依赖。`cascade-application` 已经依赖了 `cascade-graph`，所以图构建部分应该没问题。

请指示是否继续执行阶段三。
