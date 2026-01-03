简要回答

好的，我将开始执行“接口硬化”阶段的任务。本计划将定义核心的 `ReactorProtocol` 并重构 `EventDrivenRunner` 以支持依赖注入，从而解耦具体的 Python Reactor 实现。

## [WIP] refactor(vm): 定义 ReactorProtocol 并实现 EventDrivenRunner 的依赖注入

### 用户需求
执行 Cascade 3.3 架构演进路线图的第一阶段：接口硬化。具体包括：
1.  定义 `ReactorProtocol` 协议，抽象 `Reactor` 的行为。
2.  重构 `EventDrivenRunner`，移除对 `Reactor` 具体类的硬编码依赖，转而使用 `reactor_factory` 进行依赖注入。

### 评论
这是迈向“双引擎共生”的关键一步。通过引入协议和工厂模式，我们为后续无缝接入 Rust 实现的 Reactor (`cascade-vm-rs`) 扫清了障碍，同时保持了现有 Python 测试套件的兼容性。

### 目标
1.  创建 `packages/cascade-vm/src/cascade/vm/protocols.py`。
2.  在 `packages/cascade-vm/src/cascade/vm/__init__.py` 中导出新协议。
3.  修改 `packages/cascade-vm/src/cascade/vm/harness.py`，使 `EventDrivenRunner` 支持 `reactor_factory` 参数。

### 基本原理
-   **协议定义**: 使用 Python 的 `typing.Protocol` 定义 `Reactor` 的鸭子类型接口，确保静态类型检查的正确性。
-   **依赖注入**: 在 `EventDrivenRunner.__init__` 中增加 `reactor_factory` 参数（默认值为现有的 `Reactor` 类），使得测试代码可以通过注入不同的工厂来切换底层引擎，而无需修改测试逻辑。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/interfaces #scope/core #ai/instruct #task/domain/vm #task/object/reactor-interface #task/action/hardening #task/state/begin

---

### Script

#### Acts 1: 定义 ReactorProtocol

新建协议文件，定义 `Reactor` 必须暴露的公共接口。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Callable, Awaitable, Any, Dict
from cascade.spec.physics import Token

class ReactorProtocol(Protocol):
    """
    Protocol defining the interface for a Cascade Reactor.
    This allows swapping the Python implementation with a Rust-based one.
    """
    active_task_count: int

    def prime(self) -> None:
        """Inject initial potential energy into the system."""
        ...

    async def step(self) -> int:
        """
        Perform one reaction step.
        Returns the number of tasks fired.
        """
        ...

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None:
        """Register a callback to receive tokens emitted by a specific port."""
        ...
~~~~~

#### Acts 2: 导出协议

更新 `__init__.py` 以公开新定义的协议。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/__init__.py
~~~~~
~~~~~python.old
from .resource_registry import ResourceRegistry

__all__ = ["ResourceRegistry"]
~~~~~
~~~~~python.new
from .resource_registry import ResourceRegistry
from .protocols import ReactorProtocol

__all__ = ["ResourceRegistry", "ReactorProtocol"]
~~~~~

#### Acts 3: 重构 EventDrivenRunner

修改 `EventDrivenRunner` 以支持注入 `Reactor` 工厂。这将解除 Runner 与具体 `Reactor` 类的强耦合。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.observer import ObservedEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()

        # 1. Setup Resource Registry and Observability Queue
        self.event_queue: asyncio.Queue[ObservedEvent] = asyncio.Queue()
        self._captured_events: List[ObservedEvent] = []
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.observer.queue", self.event_queue)

        # 2. The function map is now used directly
        self.function_map = function_map

        # 3. Inject the registry into the Reactor
        self.reactor = Reactor(
            self.graph,
            self.memory,
            self.executor,
            self.function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
~~~~~
~~~~~python.new
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.observer import ObservedEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventTimeoutError(TimeoutError):
    pass


class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
        self.executor = PhysicsExecutor()

        # 1. Setup Resource Registry and Observability Queue
        self.event_queue: asyncio.Queue[ObservedEvent] = asyncio.Queue()
        self._captured_events: List[ObservedEvent] = []
        self.resource_registry = ResourceRegistry()
        self.resource_registry.register("system.observer.queue", self.event_queue)

        # 2. The function map is now used directly
        self.function_map = function_map

        # 3. Inject the registry into the Reactor
        # Use provided factory or default to the Python Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.executor,
            self.function_map,
            self.resource_registry,
        )
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
~~~~~

### 下一步建议

我们已经完成了“接口硬化”阶段的核心工作。

下一步，我们应该进入“第二阶段：数据纯化 (Data Purification)”。这包括：
1.  创建一个测试工具 `test_graph_purity.py`，用于验证生成的 `BipartiteGraph` 是否包含不可序列化的对象。
2.  审计并统一所有物理层函数的签名，确保它们符合 `async def (inputs, node, resources) -> dict` 的标准。

我建议先从 **任务 2.1: 图数据审计与序列化测试** 开始，因为这将揭示我们目前有多少“不纯”的数据混入了图中。
