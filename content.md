当然，这是由于我们修改了 `Machine` 的构造函数签名，但没有更新测试用例中的调用所导致的。这完全在我预料之中，是测试驱动开发中的正常步骤。

我将生成一个计划来修复这些测试，主要是为测试环境装配上新引入的 `ChronosService`。

## [WIP] fix(tests): 更新 Machine 实例化以适配 ChronosService

### 错误分析
在上一个计划中，我们向 `Machine.__init__` 添加了 `chronos_service` 参数。这导致所有直接实例化 `Machine` 的测试用例因缺少必要的参数而失败。`TypeError: Machine.__init__() missing 1 required positional argument` 明确指出了这个问题。

### 用户需求
修复因 `Machine` 构造函数签名变更而失败的集成测试。

### 评论
这是一个标准的“红-绿-重构”循环中的“红”到“绿”阶段。测试失败验证了我们的修改产生了预期的 API 变更，现在我们需要让测试代码遵循新的契约。修复这些测试也将确保 `ChronosService` 在测试环境中被正确地初始化和集成。

### 目标
1.  在 `test_lifecycle_signals.py` 的 `machine_components` fixture 中，创建并提供 `ChronosService` 实例。
2.  更新 `test_lifecycle_signals.py` 中的测试函数，以正确地接收并使用新的 `chronos_service`。
3.  在 `test_machine_integration.py` 的测试函数 `test_machine_self_terminating_flow` 中，创建并提供 `ChronosService` 实例。

### 基本原理
测试环境必须与生产环境的组件装配方式保持一致。通过在测试设置中添加 `ChronosService` 和其所需的 `chronos_queue`，我们不仅能修复 `TypeError`，还能确保测试覆盖到新服务与 `Machine` 之间的交互，从而保证系统的整体健壮性。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/time #task/domain/testing #task/object/integration-tests #task/action/update #task/state/continue

---

### Script

#### Acts 1: 修复 `test_lifecycle_signals.py`

我们首先更新 `machine_components` fixture 来创建和返回 `ChronosService`，然后更新使用该 fixture 的两个测试。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.runtime.storage import InMemoryObjectStore

# --- DRAIN Test Helpers ---
~~~~~
~~~~~python.new
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.runtime.storage import InMemoryObjectStore

# --- DRAIN Test Helpers ---
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
@pytest.fixture
def machine_components():
    memory = VolatileMemory()
    object_store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    wakeup_event = asyncio.Event()

    code_registry = CodeRegistry()
    code_registry.register("slow_task", slow_worker_func)

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)

    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )

    return memory, resource_registry, ingress_queue, compute_service, wakeup_event
~~~~~
~~~~~python.new
@pytest.fixture
def machine_components():
    memory = VolatileMemory()
    object_store = InMemoryObjectStore()
    compute_queue = asyncio.Queue()
    ingress_queue = asyncio.Queue()
    chronos_queue = asyncio.Queue()
    wakeup_event = asyncio.Event()

    code_registry = CodeRegistry()
    code_registry.register("slow_task", slow_worker_func)

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.chronos_queue", chronos_queue)

    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )

    chronos_service = ChronosService(
        inbound_queue=chronos_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )

    return (
        memory,
        resource_registry,
        ingress_queue,
        compute_service,
        chronos_service,
        wakeup_event,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_drain_waits_for_active_task(machine_components):
    (
        memory,
        resource_registry,
        ingress_queue,
        compute_service,
        wakeup_event,
    ) = machine_components
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_drain_waits_for_active_task(machine_components):
    (
        memory,
        resource_registry,
        ingress_queue,
        compute_service,
        chronos_service,
        wakeup_event,
    ) = machine_components
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, wakeup_event)

    # Inject inputs
    memory.put(d_start, Token(payload=5))  # Use an integer for the slow_worker
~~~~~
~~~~~python.new
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # Inject inputs
    memory.put(d_start, Token(payload=5))  # Use an integer for the slow_worker
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_error_signal_shuts_down_machine(machine_components):
    (
        memory,
        resource_registry,
        ingress_queue,
        compute_service,
        wakeup_event,
    ) = machine_components
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_error_signal_shuts_down_machine(machine_components):
    (
        memory,
        resource_registry,
        ingress_queue,
        compute_service,
        chronos_service,
        wakeup_event,
    ) = machine_components
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, wakeup_event)

    memory.put(d_err, Token("die"))
~~~~~
~~~~~python.new
    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    memory.put(d_err, Token("die"))
~~~~~

#### Acts 2: 修复 `test_machine_integration.py`

这个测试有自己的独立设置，我们需要同样为它添加 `ChronosService`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.storage import InMemoryObjectStore
~~~~~
~~~~~python.new
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.services.contracts import DelayRequest
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.storage import InMemoryObjectStore
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    # Communication Queues & Events
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
    wakeup_event = asyncio.Event()

    # Event Bus (Connecting the missing piece)
~~~~~
~~~~~python.new
    # Communication Queues & Events
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
    wakeup_event = asyncio.Event()

    # Event Bus (Connecting the missing piece)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    # Resource Registry
    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.event_bus", event_bus)

    # Instantiate Core Components
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    machine = Machine(reactor, compute_service, wakeup_event)

    # 2. Prime the System
    initial_value = 10
~~~~~
~~~~~python.new
    # Resource Registry
    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.chronos_queue", chronos_queue)
    resource_registry.register("system.event_bus", event_bus)

    # Instantiate Core Components
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    chronos_service = ChronosService(
        inbound_queue=chronos_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # 2. Prime the System
    initial_value = 10
~~~~~

### 下一步建议
测试已修复，`ChronosService` 已成功集成到我们的测试和运行时环境中。现在，我们可以满怀信心地执行路线图的第三步：**实现 `std.system.sleep` IC**。这将是第一个真正利用到我们新构建的时间服务的物理层组件。
