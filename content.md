好的，我将开始执行“阶段 0: 大净化”。

我的首要任务是从 `cascade-vm` 的物理层中彻底根除所有异步执行的概念，为后续的纯同步内核重构奠定一个干净、无歧义的基础。根据项目计划，我将执行以下操作：

1.  **废除 `PhysicsExecutor`**: 彻底删除负责异步任务调度的 `PhysicsExecutor` 类。
2.  **净化 `Reactor`**: 移除 `Reactor` 对 `PhysicsExecutor` 的依赖，并删除其内部所有与异步任务管理相关的状态（`active_task_count`）和方法（`_schedule_task`, `_execute_task`）。

这将使 `Reactor` 暂时处于一个非功能状态，这是为“阶段 1”的直驱引擎实现做准备的必要步骤。

## [WIP] refactor(vm): 废除异步执行器并净化 Reactor

### 用户需求

开始实施“Cascade VM - 奇点内核重构”计划的“阶段 0: 大净化”。具体行动包括：
1.  删除 `PhysicsExecutor`。
2.  从 `Reactor` 中移除相关的异步依赖和内部状态管理。

### 评论

这是一个激进而正确的开始。通过外科手术式地移除旧的异步执行模型，我们确保了新架构不会受到任何遗留概念的污染。这遵循了“先拆除，后重建”的高保真工程原则，是迈向更纯粹、更可预测的内核的关键一步。虽然这会暂时使 `Reactor` 的核心功能失效，但它为阶段 1 中“直驱引擎”的实现创造了必要的、清晰的条件。

### 目标

1.  删除文件 `packages/cascade-vm/src/cascade/vm/executor.py`。
2.  从 `packages/cascade-vm/src/cascade/vm/reactor.py` 中移除对 `PhysicsExecutor` 的引用。
3.  从 `Reactor` 类中删除 `self.active_task_count` 属性。
4.  从 `Reactor` 类中删除 `_schedule_task` 和 `_execute_task` 方法，并移除 `step` 方法中对它们的调用。

### 基本原理

项目计划要求将 `Reactor` 重塑为一个纯粹的同步状态机。为了达成这一目标，第一步必须是彻底清除所有现存的、基于线程池和 `asyncio.create_task` 的异步调度机制。这为后续引入一个更简单、更高效的直接函数调用模型（直驱逻辑）扫清了障碍。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/reactor #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 删除 PhysicsExecutor

首先，我们删除 `PhysicsExecutor` 的定义文件。

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/executor.py
~~~~~

#### Acts 2: 净化 Reactor 实现

接下来，我们修改 `Reactor`，移除所有与旧异步模型相关的代码。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry
~~~~~
~~~~~python.new
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue

        # State
        self.active_task_count = 0
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}
~~~~~
~~~~~python.new
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

        # State
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        if not nodes_to_fire:
            return 0

        # Schedule execution
        for node in nodes_to_fire:
            self._schedule_task(node, inputs_for_fire[node.id])

        return len(nodes_to_fire)

    def _schedule_task(self, node: PhysicsFuncNode, input_data: Dict[str, Token]):
        self.active_task_count += 1
        asyncio.create_task(self._execute_task(node, input_data))

    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
            if not func:
                raise ValueError(f"No function mapped for node {node.id}")

            # The new standard signature for all physical functions is (inputs, node, resources)
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                # Sync Kernel Activation: Direct Execution
                # For high-performance ICs (Allocator, Bleacher, etc.), we execute
                # directly on the reactor thread to avoid executor overhead.
                result_tokens = func(input_data, node, self.resource_registry)

            if not isinstance(result_tokens, dict):
                raise ValueError(
                    f"Function for node {node.id} must return a Dict[str, Token], "
                    f"got {type(result_tokens)}"
                )

            # 2. Emission & Sinks
            outbound = self._outbound_channels.get(node.id, [])
            node_sinks = self.sinks.get(node.id, {})

            # We iterate over all result tokens to handle both Sinks and Channels
            for port_name, token in result_tokens.items():
                if token is None:
                    continue

                # A. Handle Sinks (Direct callback)
                if port_name in node_sinks:
                    for cb in node_sinks[port_name]:
                        try:
                            res = cb(token)
                            if inspect.isawaitable(res):
                                await res
                        except Exception as e:
                            logger.exception(
                                f"Sink callback failed for {node.id}:{port_name}: {e}"
                            )

                # B. Handle Outbound Channels (Topological Flow)
                # Find channels connected to this source port
                matching_channels = [c for c in outbound if c.source_port == port_name]

                for channel in matching_channels:
                    target_node = self.graph.nodes[channel.target_node_id]
                    if isinstance(target_node, PhysicsDataNode):
                        self.memory.put(target_node, token)

        except Exception as e:
            logger.exception(f"Error executing task {node.id}: {e}")
            # TODO: Emit error token to a special error port or DLQ?
            # For now, we just log. In v3.0 specs, errors are propagated as tokens.
            # If the func raised, it means it crashed HARD.
        finally:
            self.active_task_count -= 1
            # If we hit 0, we might want to signal an event?
            # For now, relying on memory mutation events is enough for forward progress.
~~~~~
~~~~~python.new
        if not nodes_to_fire:
            return 0

        # --- EXECUTION LOGIC REMOVED ---
        # The logic to call _schedule_task was here.
        # It is removed as part of Phase 0 purification.
        # Phase 1 will implement the new direct-drive logic.

        return len(nodes_to_fire)
~~~~~

### 下一步建议

我们已经完成了“大净化”阶段，成功移除了所有旧的异步执行逻辑。

下一步是实施**“阶段 1: 直驱引擎 - `Reactor` 的重生”**。这包括：
1.  将 `Reactor.step()` 从 `async def` 修改为同步的 `def`。
2.  在 `step` 方法中实现新的“直驱”逻辑，直接同步调用函数并处理结果。
3.  创建一个新的顶层异步协调器 `Engine` 类来管理 `Reactor` 的同步循环。

如果你同意，我将为你生成实施阶段 1 的计划。
