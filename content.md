## [WIP] refactor: 消除 SDK 与 Core 之间的代码重复

### 用户需求
修复由 `check_dry_violations.py` 发现的 `src` 目录下的代码重复问题，具体针对 `LazyFactory` 协议和 `ToolEvent` 系列类。

### 评论
消除这些重复将确保类型的一致性，并防止未来在修改一个定义时忘记修改另一个定义的错误。将工具事件下沉到 `spec` 层也符合 Cascade 的架构分层原则：规范 (Spec) 定义数据形状，应用 (App/SDK) 使用它们。

### 目标
1.  在 `packages/cascade-spec/src/cascade/spec/tooling.py` 中集中定义 `ToolEvent`, `PlanAnalysisStarted` 等类。
2.  重构 `packages/cascade-application/src/cascade/app/__init__.py` 以导入上述类。
3.  重构 `packages/cascade-sdk/src/cascade/tools/events.py` 以导入上述类（或者如果该文件仅包含这些定义，则考虑删除该文件并更新引用）。
4.  修改 `packages/cascade-sdk/src/cascade/providers/registry.py`，从 `cascade.spec.protocols` 导入 `LazyFactory` 而不是重新定义。

### 基本原理
*   **LazyFactory**: `cascade-spec` 是协议定义的权威来源。
*   **ToolEvent**: 这些事件代表了系统行为的契约（例如 Dry Run 的输出格式）。将它们移至 `cascade-spec` 使得契约明确且共享。

### 标签
#intent/refine #flow/ready #priority/medium #comp/interfaces #scope/core #ai/instruct #task/domain/refactoring #task/object/dry-compliance #task/action/deduplicate #task/state/begin

---

### Script

#### Acts 1: 创建 Tooling Spec 定义

**解决方案**: 我们需要在 `cascade-spec` 中定义一个纯粹的 `ToolEvent` 数据结构，或者承认这些事件属于 Runtime 层面。
鉴于 `Event` 基类包含 `run_id`, `timestamp` 等运行时信息，它确实属于 Runtime。
但是，`cascade-application` 和 `cascade-sdk` 都依赖 `cascade-engine`。
所以，正确的去重位置应该是 **`cascade-engine`**，或者保持在 `cascade-application` 中并让 SDK 引用它。
考虑到这些事件是由 `CascadeApp` (在 `cascade-application` 中) 产生的，它们应该定义在哪里？
`CascadeApp` 使用 `DryRunConsoleSubscriber` 来消费这些事件。
最好的位置是 `cascade.runtime.events` (在 `cascade-engine` 包中)，因为它们是 `Event` 的子类。

让我们重新调整 Acts 1：将这些类移动到 `packages/cascade-engine/src/cascade/runtime/events.py`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/events.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class ConnectorDisconnected(Event):
    pass
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class ConnectorDisconnected(Event):
    pass


# --- Tooling Events ---


@dataclass(frozen=True)
class ToolEvent(Event):
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    target_node_id: str = ""

    def _get_payload(self) -> Dict[str, Any]:
        return {"target_node_id": self.target_node_id}


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def _get_payload(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "total_nodes": self.total_nodes,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "input_bindings": self.input_bindings,
        }


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    total_steps: int = 0

    def _get_payload(self) -> Dict[str, Any]:
        return {"total_steps": self.total_steps}
~~~~~

#### Acts 2: 更新 Cascade Application

现在我们可以从 `cascade.runtime.events` 导入这些类，而不是在 `__init__.py` 中重新定义。

~~~~~act
read_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers ---


@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    return list(args)


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
) -> Optional[Callable[[str], StateBackend]]:
    if backend_spec is None:
        return None

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
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def _get_node_shape(node: Node) -> str:
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    return "box"


# --- Tool Events (Scoped to Application Layer for now) ---


@dataclass(frozen=True)
class ToolEvent(Event):
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    target_node_id: str = ""


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    index: int = 0
    total_nodes: int = 0
    node_id: str = ""
    node_name: str = ""
    input_bindings: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    total_steps: int = 0


class DryRunConsoleSubscriber:
~~~~~
~~~~~python.new
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    Event,
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)
from cascade.runtime.subscribers import HumanReadableLogSubscriber, TelemetrySubscriber
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


# --- Internal Helpers ---


@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    return list(args)


def _create_state_backend_factory(
    backend_spec: Union[str, Callable[[str], StateBackend], None],
) -> Optional[Callable[[str], StateBackend]]:
    if backend_spec is None:
        return None

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
            client = redis.from_url(backend_spec)

            def factory(run_id: str) -> StateBackend:
                return RedisStateBackend(run_id=run_id, client=client)

            return factory
        else:
            raise ValueError(f"Unsupported state backend URI scheme: {backend_spec}")

    raise TypeError(f"Invalid state_backend type: {type(backend_spec)}")


def _get_node_shape(node: Node) -> str:
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    return "box"


class DryRunConsoleSubscriber:
~~~~~

#### Acts 3: 删除 SDK 中的冗余定义

`packages/cascade-sdk/src/cascade/tools/events.py` 现在完全多余了，因为所有定义都已在 `runtime.events` 中，或者应该从那里导入。为了保持 SDK 的导出结构，我们将修改它以重导出这些类。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/tools/events.py
~~~~~
~~~~~python
from cascade.runtime.events import (
    ToolEvent,
    PlanAnalysisStarted,
    PlanNodeInspected,
    PlanAnalysisFinished,
)

__all__ = [
    "ToolEvent",
    "PlanAnalysisStarted",
    "PlanNodeInspected",
    "PlanAnalysisFinished",
]
~~~~~

#### Acts 4: 修复 SDK 中的 LazyFactory 重复

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/providers/registry.py
~~~~~
~~~~~python.old
import sys
import importlib.metadata
from typing import Any, Dict, Protocol


class LazyFactory(Protocol):
    def map(self, **kwargs) -> Any: ...
    def __call__(self, *args, **kwargs) -> Any: ...


class Provider(Protocol):
~~~~~
~~~~~python.new
import sys
import importlib.metadata
from typing import Any, Dict, Protocol
from cascade.spec.protocols import LazyFactory


class Provider(Protocol):
~~~~~

### 下一步建议
运行 `scripts/check_dry_violations.py` 验证修复效果。`LazyFactory` 和 `ToolEvent` 相关的警告应该消失。
