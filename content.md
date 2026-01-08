简要回答
执行集成操作。这将涉及三个组件的修改：修正 `PhysicsKernel` 的类型签名（Token vs Ref），重构 `Reactor` 以使用内核，并在 `EventDrivenRunner` 中进行组装。

## [WIP] refactor(vm): integrate PhysicsKernel into Reactor

### 用户需求
将 `PhysicsKernel` 正式集成到 `Reactor` 中，以实现拓扑逻辑与执行逻辑的解耦。这解决了 `Reactor` 职责过载的问题，并为未来潜在的内核替换或优化铺平道路。

### 评论
这是一个关键的架构重构。虽然代码量不大，但它纠正了组件间的层级关系。这也是修复 `PhysicsKernel` 中潜在类型定义错误（它目前错误地引用了 `Ref` 而非 `Token`）的好机会。

### 目标
1.  **修正 `PhysicsKernel`**: 将其输入输出签名从 `Ref` 更正为 `Token`，以匹配标准库 IC 的实际行为。
2.  **重构 `Reactor`**: 移除 `function_map` 和 `resource_registry` 依赖，转而依赖 `PhysicsKernel` 实例。在 `step()` 中委托内核执行任务。
3.  **更新 `EventDrivenRunner`**: 在组装阶段实例化 `PhysicsKernel` 并注入 `Reactor`。

### 基本原理
目前 `Reactor` 直接持有函数映射和资源注册表，不仅违反了关注点分离原则，也使得 `PhysicsKernel` 这个本来定义好的抽象沦为摆设。通过这次重构，我们将恢复架构设计的初衷：`Reactor` 负责物理场（Token 流动），`Kernel` 负责原子反应（IC 执行）。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/physics-kernel #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 修正 PhysicsKernel 的类型定义
目前的 `PhysicsKernel` 错误地使用了 `Ref` 作为输入输出单位。实际上，物理层的 IC 是基于 `Token` 工作的（Token 包含 Payload 和 Trace）。我们需要修正这一点。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/kernel/core.py
~~~~~
~~~~~python.old
from typing import Callable, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Ref]
KernelFunc = Callable[
    [Dict[str, Ref], PhysicsFuncNode, ResourceRegistry], Dict[str, Ref]
]


class PhysicsKernel:
    def __init__(
        self, function_map: Dict[str, KernelFunc], resources: ResourceRegistry
    ):
        self._function_map = function_map
        self._resources = resources

    def execute(self, node: PhysicsFuncNode, inputs: Dict[str, Ref]) -> Dict[str, Ref]:
        func = self._function_map.get(node.id)
        if not func:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            raise e
~~~~~
~~~~~python.new
from typing import Callable, Dict

from cascade.spec.physical.nodes import PhysicsFuncNode, Token
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Token], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Token]
KernelFunc = Callable[
    [Dict[str, Token], PhysicsFuncNode, ResourceRegistry], Dict[str, Token]
]


class PhysicsKernel:
    def __init__(
        self, function_map: Dict[str, KernelFunc], resources: ResourceRegistry
    ):
        self._function_map = function_map
        self._resources = resources

    def execute(
        self, node: PhysicsFuncNode, inputs: Dict[str, Token]
    ) -> Dict[str, Token]:
        func = self._function_map.get(node.id)
        if not func:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            raise e
~~~~~

#### Acts 2: 重构 Reactor 以使用 PhysicsKernel
我们将修改 `Reactor`，使其不再直接管理函数和资源，而是通过 `PhysicsKernel` 接口进行交互。这简化了 `step` 方法的逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from typing import List, Callable, Dict, Tuple, Awaitable, Optional, Any
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue

        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()
~~~~~
~~~~~python.new
from typing import List, Callable, Dict, Tuple, Awaitable, Optional, Any
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.kernel import PhysicsKernel

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        kernel: PhysicsKernel,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.kernel = kernel
        self.ingress_queue = ingress_queue

        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        # --- DIRECT DRIVE EXECUTION ---
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Synchronous Execution
                func = self.function_map.get(node.id)
                if not func:
                    raise ValueError(f"No function mapped for node {node.id}")

                results = func(inputs, node, self.resource_registry)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                logger.exception(f"Kernel panic at node '{node.id}': {e}")
                # Upgrade kernel panic to System Error Signal
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )

        return len(nodes_to_fire)
~~~~~
~~~~~python.new
        # --- DIRECT DRIVE EXECUTION ---
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Synchronous Execution via Kernel
                results = self.kernel.execute(node, inputs)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                # Kernel panic is already logged by the kernel, but we handle the signal here
                # Upgrade kernel panic to System Error Signal
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )

        return len(nodes_to_fire)
~~~~~

#### Acts 3: 在 Harness 中组装 PhysicsKernel
最后，我们需要更新 `EventDrivenRunner`，在创建 `Reactor` 之前先组装 `PhysicsKernel`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.services.observability.bus import EventBus
~~~~~
~~~~~python.new
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.runtime.services.observability.bus import EventBus
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            function_map,
            self.resource_registry,
            ingress_queue=self.ingress_queue,
        )
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine
~~~~~
~~~~~python.new
        self.resource_registry.register("system.chronos_queue", self.chronos_queue)
        self.resource_registry.register("system.object_store", self.object_store)

        # 4. Setup Reactor
        # Construct the Physics Kernel
        self.kernel = PhysicsKernel(function_map, self.resource_registry)

        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.kernel,
            ingress_queue=self.ingress_queue,
        )
        # The Machine is now a component managed by the harness
        from cascade.vm.machine import Machine
~~~~~

### 下一步建议
运行测试以确保此次重构没有破坏现有的执行流程。特别是 `test_reactor.py` 可能需要更新，因为我们更改了 `Reactor` 的构造函数签名。
