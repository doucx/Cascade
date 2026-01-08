好的，我们来执行这个架构修正。集成 `PhysicsKernel` 将使 `Reactor` 的职责更加纯粹，符合我们追求的“本体论正确性”。

我将生成一个计划，通过修改 `PhysicsKernel`、`Reactor` 和 `EventDrivenRunner` 来完成这次集成。

我已完成计划，请确认。

## [WIP] refactor(vm): 将 PhysicsKernel 集成到 Reactor 执行循环中

### 用户需求

`PhysicsKernel` 抽象虽已定义但未被使用，导致 `Reactor` 直接处理函数执行，这违反了关注点分离原则。目标是集成 `PhysicsKernel`，使其作为 `Reactor` 和具体 IC（集成电路/内核函数）实现之间的执行层。

### 评论

这是一次关键的架构精炼。它将 `Reactor` 塑造为一个纯粹的拓扑引擎，将其与 Python 函数执行的具体细节解耦，并为处理“内核恐慌”建立了清晰的边界。此举完全符合高保真工程公理（HFEA）。

### 目标

1.  重构 `PhysicsKernel` 以存储 `function_map` 和 `resource_registry`，并实现核心执行逻辑。
2.  将 `Reactor.step` 中的执行逻辑（包括异常处理）迁移到 `PhysicsKernel.execute` 中。
3.  更新 `Reactor` 的构造函数，使其接收一个 `PhysicsKernel` 实例，而不是 `function_map` 和 `resource_registry`。
4.  更新 `EventDrivenRunner`（测试工具）以正确组装 `PhysicsKernel` 并将其注入到 `Reactor` 中。

### 基本原理

当前的实现混合了拓扑状态管理（`Reactor` 的职责）和执行逻辑（`Kernel` 的职责）。通过在 `EventDrivenRunner` 中创建 `PhysicsKernel` 实例并将其传递给 `Reactor`，我们强制执行了严格的依赖层次结构：`Harness -> Kernel -> Reactor`。`Reactor` 不再需要知道函数是如何被调用的或它们需要什么资源，只需知道 `Kernel` 可以执行它们。这使得系统更加模块化、可测试和健壮。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #concept/executor #scope/core #ai/brainstorm #task/domain/vm #task/object/kernel-integration #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 强化 `PhysicsKernel` 并定义正确的执行契约

我们将重写 `PhysicsKernel`，使其成为真正的执行核心。它将持有 `function_map` 和 `resources`，并处理执行过程中的异常。同时，我们将修正 `KernelFunc` 的类型提示，使其操作 `Token` 而非 `Ref`，因为 `Token` 是物理层流动的基本单位，其载荷（payload）才是 `Ref`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/kernel/core.py
~~~~~
~~~~~python
import logging
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
            # This should ideally be caught by the Linker, but as a safeguard:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            # Re-raise to allow the Reactor to handle it as a system-level error.
            raise
~~~~~

#### Acts 2: 重构 `Reactor` 以委托执行给 `Kernel`

现在，我们将修改 `Reactor`。它的构造函数将接收 `PhysicsKernel`，并移除对 `function_map` 和 `resource_registry` 的直接依赖。`step` 方法中的执行部分将被简化为对 `self.kernel.execute` 的一次调用。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
from cascade.vm.memory import VolatileMemory
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry

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
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Delegate execution to the kernel
                results = self.kernel.execute(node, inputs)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                # The kernel already logged the panic. The Reactor's job is to
                # escalate it to a system-level control signal.
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )
~~~~~

#### Acts 3: 更新 `EventDrivenRunner` 以正确组装 `Kernel` 和 `Reactor`

最后，我们修改测试工具 `EventDrivenRunner`，它扮演着“策略层”的角色，负责正确地组装所有组件。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.vm.reactor import Reactor
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
~~~~~
~~~~~python.new
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        # 4. Setup Kernel & Reactor
        self.kernel = PhysicsKernel(function_map, self.resource_registry)
        factory = reactor_factory or Reactor
        self.reactor = factory(
            self.graph,
            self.memory,
            self.kernel,
            ingress_queue=self.ingress_queue,
        )
        # The Machine is now a component managed by the harness
~~~~~

### 下一步建议

核心逻辑已重构。下一步最关键的是为 `cascade-vm` 运行测试套件，以确保我们的更改没有引入任何回归。特别是与 `Reactor` 执行周期和资源分配相关的测试对于验证至关重要。
