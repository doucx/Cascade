简要回答
好的，我将执行第一阶段的基础设施贯通工作。这将涉及打通 `ExecutionContext` 以携带 `ResourceContainer`，并更新 `Engine`、`RuntimeHarness` 和 `BridgedComputeService` 的初始化逻辑，从而为后续的依赖注入修复建立数据通路。

## [WIP] refactor(compute): 贯通 ResourceContainer 至计算适配层

### 用户需求
用户希望修复计算适配层无法处理 `Inject` 和 `params_context` 的问题。第一步是建立基础设施连接，确保 `BridgedComputeService` 能够访问到 `ResourceContainer` 和 `ExecutionContext`。

### 评论
这是一个必要的架构调整。目前计算服务 (`BridgedComputeService`) 是作为孤岛运行的，只知道如何执行代码，却不知道代码运行的上下文环境。通过注入 `ExecutionContext`（其中包含 `ResourceContainer`），我们为适配层赋予了“上下文感知”能力。

### 目标
1.  修改 `cascade-spec` 中的 `ExecutionContext`，使其包含 `resource_container` 字段。
2.  修改 `cascade-vm` 中的 `BridgedComputeService`，使其构造函数接收并存储 `ExecutionContext`。
3.  修改 `cascade-runtime` 中的 `Engine`，在创建 `ExecutionContext` 时注入资源容器。
4.  修改 `cascade-runtime` 中的 `RuntimeHarness`，在初始化计算服务时传递上下文。

### 基本原理
依赖注入解析需要在运行时查找资源提供者，而这些提供者存储在 `ResourceContainer` 中。`BridgedComputeService` 是实际执行任务逻辑的地方，因此它必须持有对 `ResourceContainer` 的引用。最自然的传递路径是通过 `ExecutionContext`，因为它已经封装了每次运行的特定状态。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/runtime #comp/vm #scope/core #task/domain/compute #task/object/adapter-layer #task/action/wiring #task/state/begin

---

### Script

#### Acts 1: 更新 ExecutionContext 定义

首先，我们在规范中扩展执行上下文，增加 `resource_container` 字段。使用 `Any` 类型以避免规范层对运行时实现的循环依赖。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
~~~~~
~~~~~python.old
@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    object_store: ObjectStore
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass
class ExecutionContext:
    run_id: str
    state_backend: StateBackend
    object_store: ObjectStore
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    resource_container: Any = None
~~~~~

#### Acts 2: 更新 BridgedComputeService 签名

接着，修改 VM 层的计算服务适配器，使其能够接收并保存上下文对象。这是后续实现依赖注入逻辑的基础。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest

logger = logging.getLogger(__name__)
~~~~~
~~~~~python.new
from cascade.spec.runtime.interfaces import Executor
from ..registry import CodeRegistry
from cascade.spec.runtime import ComputeRequest, ExecutionContext

logger = logging.getLogger(__name__)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/adapters.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        executor: Executor,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.executor = executor
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._wakeup_event = wakeup_event
        self._running = False
        self._active_count = 0
~~~~~
~~~~~python.new
    def __init__(
        self,
        executor: Executor,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        context: ExecutionContext,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.executor = executor
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self.context = context
        self._wakeup_event = wakeup_event
        self._running = False
        self._active_count = 0
~~~~~

#### Acts 3: 更新 Engine 初始化逻辑

在 Runtime 层，我们需要在 `Engine` 启动运行时将 `resource_container` 注入到上下文中。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    object_store=self.object_store,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(
~~~~~
~~~~~python.new
                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    object_store=self.object_store,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                    resource_container=self.resource_container,
                )

                final_result = await strategy.execute(
~~~~~

#### Acts 4: 更新 RuntimeHarness 传递逻辑

最后，在 VM 策略的 `RuntimeHarness` 中，将准备好的 `context` 传递给 `BridgedComputeService`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        self.compute_service = BridgedComputeService(
            executor=executor,
            store=context.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            wakeup_event=self.wakeup_event,
        )
~~~~~
~~~~~python.new
        self.compute_service = BridgedComputeService(
            executor=executor,
            store=context.object_store,
            registry=code_registry,
            inbound_queue=self.compute_queue,
            outbound_queue=self.ingress_queue,
            context=context,
            wakeup_event=self.wakeup_event,
        )
~~~~~

### 下一步建议

基础设施已经打通。下一步应该进入**第二阶段：核心解析逻辑重构 (Core Resolution Logic)**。

你需要实现智能参数绑定逻辑：
1.  在 `BridgedComputeService` 中实现 `_bind_execution_arguments` 方法。
2.  使用 `inspect.Signature` 智能匹配输入参数、`Inject` 声明和系统上下文 (`params_context`)。
3.  实现资源解析逻辑，从 `context.resource_container` 中获取实际对象。
