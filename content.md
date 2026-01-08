好的，我来修复由 `Reactor` 构造函数签名变更引起的测试失败。这些失败分为两类：直接的 `TypeError` 和间接的 `AssertionError`（因为 Reactor 未能正确激发）。根本原因都是测试代码没有更新以使用新的 `PhysicsKernel` 抽象。

我将逐一修复这些测试文件。

## [WIP] fix(tests): adapt tests to PhysicsKernel integration

### 错误分析
在上一个 `refactor` 计划中，我更改了 `cascade.vm.reactor.Reactor` 的构造函数签名，将其从 `(graph, memory, function_map, resource_registry, ...)` 更改为 `(graph, memory, kernel, ...)`，其中 `kernel` 是一个 `PhysicsKernel` 实例。这导致了所有直接实例化 `Reactor` 的测试用例都失败了。

### 用户需求
更新所有受影响的测试用例，使其遵循新的 `Reactor` 初始化协议：即先创建 `ResourceRegistry` 和 `function_map`，用它们组装一个 `PhysicsKernel`，然后将该 `kernel` 实例传递给 `Reactor`。

### 评论
这是一个预料之中的、必要的修复。它确保了我们的测试套件与最新的架构保持一致，验证了 `PhysicsKernel` 集成的正确性。

### 目标
1.  修改 `packages/cascade-compiler/tests/integration/` 下的 `test_branching.py` 和 `test_resource_backpressure.py`。
2.  修改 `packages/cascade-vm/tests/integration/` 下的所有失败测试文件。
3.  修改 `packages/cascade-vm/tests/unit/physics/` 下的 `test_micro_physics.py`。

### 基本原理
通过在每个测试用例中遵循“组装 `Kernel` -> 注入 `Reactor`”的模式，我们可以修复所有因签名不匹配而导致的 `TypeError` 和 `AssertionError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/runtime #scope/dx #ai/instruct #task/domain/runtime #task/object/physics-kernel #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-compiler` 包中的集成测试

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
import pytest
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor


def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~
~~~~~python.new
import pytest
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry


def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_branching_path_a(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel(func_map, resources)
    reactor = Reactor(graph, memory, kernel)

    # 1. Inject signal for Path A
    memory.put(d_in, Token(payload="path_a"))
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, func_map)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_branching_path_b(branching_topology):
    graph, d_in, d_a, d_b, func_map = branching_topology

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel(func_map, resources)
    reactor = Reactor(graph, memory, kernel)

    # 1. Inject signal for Path B
    memory.put(d_in, Token(payload="path_b"))
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.runtime.storage import InMemoryObjectStore
~~~~~
~~~~~python.new
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.runtime.storage import InMemoryObjectStore
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)

    reactor = Reactor(physical_graph, memory, func_map, resource_registry=registry)

    # 6. Prime the reactor.
    reactor.prime()
~~~~~
~~~~~python.new
    registry = ResourceRegistry()
    store = InMemoryObjectStore()
    registry.register("system.object_store", store)

    kernel = PhysicsKernel(func_map, registry)
    reactor = Reactor(physical_graph, memory, kernel)

    # 6. Prime the reactor.
    reactor.prime()
~~~~~

#### Acts 2: 修复 `cascade-vm` 包中的集成测试

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel("D_drain", "out", "F_drain", "in"))

    func_map = {"F_launch": mock_dispatcher_kernel, "F_drain": drain_trigger_kernel}

    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # Inject inputs
    memory.put(d_start, Token(payload=5))  # Use an integer for the slow_worker
~~~~~
~~~~~python.new
    graph.channels.append(Channel("D_drain", "out", "F_drain", "in"))

    func_map = {"F_launch": mock_dispatcher_kernel, "F_drain": drain_trigger_kernel}

    kernel = PhysicsKernel(func_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # Inject inputs
    memory.put(d_start, Token(payload=5))  # Use an integer for the slow_worker
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel("D_err", "out", "F_crash", "in"))

    func_map = {"F_crash": crashing_kernel}

    reactor = Reactor(graph, memory, func_map, resource_registry, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    memory.put(d_err, Token("die"))
~~~~~
~~~~~python.new
    graph.channels.append(Channel("D_err", "out", "F_crash", "in"))

    func_map = {"F_crash": crashing_kernel}

    kernel = PhysicsKernel(func_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    memory.put(d_err, Token("die"))
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    resource_registry.register("system.chronos_queue", chronos_queue)
    resource_registry.register("system.event_bus", event_bus)

    # Instantiate Core Components
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
~~~~~
~~~~~python.new
    resource_registry.register("system.chronos_queue", chronos_queue)
    resource_registry.register("system.event_bus", event_bus)

    # Instantiate Core Components
    kernel = PhysicsKernel(function_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor


def noop_producer(inputs, node, resources):
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory, MemoryFullError
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry


def noop_producer(inputs, node, resources):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
    # Both F_p1 and F_p2 are ready. They will try to fire in the same step.
~~~~~
~~~~~python.new
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    func_map = {f_p1.id: noop_producer, f_p2.id: noop_producer}
    kernel = PhysicsKernel(func_map, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # 2. Execution
    # Both F_p1 and F_p2 are ready. They will try to fire in the same step.
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(
        graph,
        memory,
        {f_p1.id: noop_producer, f_p2.id: noop_producer},
    )
    reactor.prime()

    # 2. Execution
~~~~~
~~~~~python.new
    graph.channels.append(Channel(f_p2.id, "out", d_life.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    func_map = {f_p1.id: noop_producer, f_p2.id: noop_producer}
    kernel = PhysicsKernel(func_map, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # 2. Execution
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor


def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~
~~~~~python.new
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry


def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, function_map)

    # 1. Start state
    initial_token = Token(payload=10)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_ping_pong_flow(ping_pong_topology):
    graph, d1, f1, d2, function_map = ping_pong_topology

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel(function_map, resources)
    reactor = Reactor(graph, memory, kernel)

    # 1. Start state
    initial_token = Token(payload=10)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_time_services.py
~~~~~
~~~~~python.old
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.registry import CodeRegistry
~~~~~
~~~~~python.new
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.registry import CodeRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_time_services.py
~~~~~
~~~~~python.old
    # Map the kernel function
    function_map = {f_sleep_id: standard_sleep}

    # 3. Instantiate Services & Machine
    reactor = Reactor(graph, memory, function_map, resource_registry, ingress_queue)

    compute_service = LocalComputeService(
        store=object_store,
~~~~~
~~~~~python.new
    # Map the kernel function
    function_map = {f_sleep_id: standard_sleep}

    # 3. Instantiate Services & Machine
    kernel = PhysicsKernel(function_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)

    compute_service = LocalComputeService(
        store=object_store,
~~~~~

#### Acts 3: 修复 `cascade-vm` 包中的单元测试

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal
~~~~~
~~~~~python.new
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
    def identity(inputs, node, res):
        return {"out": inputs["in"]}

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, {f_node.id: identity})
    reactor.prime()

    # Action
~~~~~
~~~~~python.new
    def identity(inputs, node, res):
        return {"out": inputs["in"]}

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_node.id: identity}, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # Action
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(f_stain.id, "obs_output", d_obs.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, {f_stain.id: standard_stainer})

    # Inject Fault
    memory.put(d_res, Token(payload=ValueError("Micro-Physics Failure")))
~~~~~
~~~~~python.new
    graph.channels.append(Channel(f_stain.id, "obs_output", d_obs.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_stain.id: standard_stainer}, resources)
    reactor = Reactor(graph, memory, kernel)

    # Inject Fault
    memory.put(d_res, Token(payload=ValueError("Micro-Physics Failure")))
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel(f_halt.id, "out", d_void.id, "in"))

    memory = VolatileMemory()
    reactor = Reactor(graph, memory, {f_halt.id: halt_signal})
    reactor.prime()

    # Pre-condition
~~~~~
~~~~~python.new
    graph.channels.append(Channel(f_halt.id, "out", d_void.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_halt.id: halt_signal}, resources)
    reactor = Reactor(graph, memory, kernel)
    reactor.prime()

    # Pre-condition
~~~~~

### 下一步建议
所有已知的测试失败都已修复。现在应该重新运行测试套件以确认所有问题都已解决，并检查是否引入了新的回归。如果一切顺利，我们可以将这个工作单元标记为 `[COMMIT]` 并提交。
