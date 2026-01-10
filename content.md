[简要回答]
测试失败的原因已从“异步错误”和“Wiring错误”转变为“运行时资源缺失”。具体来说，`RuntimeHarness` 未将 `EventBus` 注册到 VM 的资源注册表中，导致 `standard_observer` 在尝试获取 `system.event_bus` 时触发 Kernel Panic，进而导致 Machine 异常停止。

这实际上是一个好消息，证明了上一轮关于 `asyncio` 和 `Expander` 的修复已经生效（否则代码不会运行到 Observer 执行阶段）。现在的任务是补全依赖注入。

## [WIP] fix: 将 EventBus 注入 VM 运行时环境

### 错误分析
`standard_observer` 内核函数依赖于名为 `system.event_bus` 的资源来发布事件。然而，当前的 `VMExecutionStrategy` 和 `RuntimeHarness` 在初始化时没有接收或注册这个组件。导致 `KeyError: "Resource 'system.event_bus' not found."`，这被 Kernel 捕获并转化为系统级错误，终止了执行。

### 用户需求
使 `VMExecutionStrategy` 能够通过所有 E2E 测试，包括那些触发可观测性事件的测试。

### 评论
这是一个典型的集成遗漏。在基于微内核的架构中，所有外部能力（如日志、事件总线）都必须显式地作为“资源”注入到内核空间。

### 目标
1.  修改 `VMExecutionStrategy` 和 `RuntimeHarness`，使其在构造时接受 `EventBus`。
2.  在 `RuntimeHarness` 中将 `EventBus` 注册为 `system.event_bus`。
3.  更新测试代码以匹配新的构造函数签名。

### 基本原理
通过显式的依赖注入，确保 VM 内部的 `standard_observer` 能够安全地访问宿主环境的 `EventBus`，从而打通遥测链路。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/observability #task/domain/core #task/object/vm-strategy #task/action/integration #task/state/end

---

### Script

#### Acts 1: 更新 `VMExecutionStrategy` 和 `RuntimeHarness`

我们需要在 `VMExecutionStrategy` 和 `RuntimeHarness` 的 `__init__` 方法中添加 `bus` 参数，并在 `_register_system_resources` 中进行注册。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.strategies import ExecutionStrategy, ExecutionContext
from cascade.spec.runtime.interfaces import Executor
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.assembly import CompilationArtifact
from cascade.spec.physical.object import Ref
from cascade.spec.ir.graph import GraphIR
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

from cascade.vm.compute import BridgedComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.registry import CodeRegistry
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.memory import VolatileMemory
from cascade.vm.linker import Linker

from cascade.compiler.frontend import IRGenerator, GenerationResult
from cascade.compiler.backend import Builder

logger = logging.getLogger(__name__)


class RuntimeHarness:
    """
    The 'Motherboard' for the VM instance.
    Responsible for assembling the physical environment, buses, and peripheral services
    required by the Machine to operate within the Runtime context.
    """

    def __init__(
        self,
        context: ExecutionContext,
        executor: Executor,
        code_registry: CodeRegistry,
    ):
        self.context = context

        # 1. Physical Buses (Queues)
~~~~~
~~~~~python.new
from cascade.spec.runtime.strategies import ExecutionStrategy, ExecutionContext
from cascade.spec.runtime.interfaces import Executor
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.environment import EnvironmentDef, ResourceDef
from cascade.spec.physical.assembly import CompilationArtifact
from cascade.spec.physical.object import Ref
from cascade.spec.ir.graph import GraphIR
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

from cascade.vm.compute import BridgedComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.vm.registry import CodeRegistry
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.memory import VolatileMemory
from cascade.vm.linker import Linker
from cascade.runtime.services.observability.bus import EventBus

from cascade.compiler.frontend import IRGenerator, GenerationResult
from cascade.compiler.backend import Builder

logger = logging.getLogger(__name__)


class RuntimeHarness:
    """
    The 'Motherboard' for the VM instance.
    Responsible for assembling the physical environment, buses, and peripheral services
    required by the Machine to operate within the Runtime context.
    """

    def __init__(
        self,
        context: ExecutionContext,
        executor: Executor,
        bus: EventBus,
        code_registry: CodeRegistry,
    ):
        self.context = context
        self.bus = bus

        # 1. Physical Buses (Queues)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
    def _register_system_resources(self):
        self.resource_registry.register("system.egress_queue", self.egress_queue)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register(
            "system.object_store", self.context.object_store
        )


class VMExecutionStrategy(ExecutionStrategy):
    """
    The Next-Gen Execution Strategy based on the Cascade VM (Physics Engine).

    It orchestrates the full lifecycle:
    1. Compile: Logical Graph -> Physical Assembly
    2. Link: Register executable code
    3. Bootstrap: Assemble the Machine and Harness
    4. Ignite: Inject initial energy
    5. Run: Drive the Machine loop and harvest results
    """

    def __init__(self, executor: Executor):
        self.executor = executor
        self.compiler_frontend = IRGenerator()
        self.compiler_backend = Builder()
        self.linker = Linker()

    async def execute(self, target: Any, context: ExecutionContext) -> Any:
        logger.info("VMStrategy: Starting execution cycle.")

        # --- Phase 1: Compilation ---
        logger.debug("VMStrategy: Compiling logical graph...")
        graph_ir_result = self.compiler_frontend.generate(target)
        graph_ir = graph_ir_result.ir

        # Build environment definition from IR requirements
        env_def = self._scan_resources(graph_ir)

        artifact = self.compiler_backend.build(graph_ir, environment=env_def)
        logger.debug("VMStrategy: Compilation complete.")

        # --- Phase 2: Linking ---
        logger.debug("VMStrategy: Linking code...")
        code_registry = self._link_code(graph_ir, graph_ir_result)

        # --- Phase 3: Bootstrap ---
        logger.debug("VMStrategy: Bootstrapping machine...")
        harness = RuntimeHarness(context, self.executor, code_registry)

        function_map = self.linker.link(artifact.assembly, code_registry)
        kernel = PhysicsKernel(function_map, harness.resource_registry)
~~~~~
~~~~~python.new
    def _register_system_resources(self):
        self.resource_registry.register("system.egress_queue", self.egress_queue)
        self.resource_registry.register("system.compute_queue", self.compute_queue)
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register(
            "system.object_store", self.context.object_store
        )
        self.resource_registry.register("system.event_bus", self.bus)


class VMExecutionStrategy(ExecutionStrategy):
    """
    The Next-Gen Execution Strategy based on the Cascade VM (Physics Engine).

    It orchestrates the full lifecycle:
    1. Compile: Logical Graph -> Physical Assembly
    2. Link: Register executable code
    3. Bootstrap: Assemble the Machine and Harness
    4. Ignite: Inject initial energy
    5. Run: Drive the Machine loop and harvest results
    """

    def __init__(self, executor: Executor, bus: EventBus):
        self.executor = executor
        self.bus = bus
        self.compiler_frontend = IRGenerator()
        self.compiler_backend = Builder()
        self.linker = Linker()

    async def execute(self, target: Any, context: ExecutionContext) -> Any:
        logger.info("VMStrategy: Starting execution cycle.")

        # --- Phase 1: Compilation ---
        logger.debug("VMStrategy: Compiling logical graph...")
        graph_ir_result = self.compiler_frontend.generate(target)
        graph_ir = graph_ir_result.ir

        # Build environment definition from IR requirements
        env_def = self._scan_resources(graph_ir)

        artifact = self.compiler_backend.build(graph_ir, environment=env_def)
        logger.debug("VMStrategy: Compilation complete.")

        # --- Phase 2: Linking ---
        logger.debug("VMStrategy: Linking code...")
        code_registry = self._link_code(graph_ir, graph_ir_result)

        # --- Phase 3: Bootstrap ---
        logger.debug("VMStrategy: Bootstrapping machine...")
        harness = RuntimeHarness(context, self.executor, self.bus, code_registry)

        function_map = self.linker.link(artifact.assembly, code_registry)
        kernel = PhysicsKernel(function_map, harness.resource_registry)
~~~~~

#### Acts 2: 更新 E2E 测试中的 Fixture

更新 `tests/integration/test_vm_e2e.py` 中的 `strategy` fixture，以匹配新的签名。

~~~~~act
patch_file
packages/cascade-runtime/tests/integration/test_vm_e2e.py
~~~~~
~~~~~python.old
@pytest.fixture
def strategy(executor):
    return VMExecutionStrategy(executor=executor)
~~~~~
~~~~~python.new
@pytest.fixture
def strategy(executor, bus):
    return VMExecutionStrategy(executor=executor, bus=bus)
~~~~~

### 下一步建议

重新运行 `test_vm_e2e.py`。我有极高的信心，这次所有测试都将通过。
如果测试全绿，那么 `VMExecutionStrategy` 的 MVP (最小可行产品) 就正式完成了，我们可以将其视为 `beta` 状态并进行更复杂的场景测试。
