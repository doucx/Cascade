好的，我们现在进入 GREEN 阶段。

这个计划将修改 `Reactor` 的核心逻辑，使其能够感知并遵守 `ResourceManager` 施加的约束。这将修复在 RED 阶段引入的两个测试失败，使我们进入 GREEN 状态。

## [WIP] feat(vm): implement resource-aware reactor

### 用户需求
修改 `Reactor` 实现，使其通过 `ResourceManager` 感知资源限制，并在资源释放后唤醒等待中的任务，以通过 Phase 4 的 TDD 测试。

### 评论
这是一个关键的架构增强，将 `Reactor` 从一个简单的、数据驱动的调度器，转变为一个具备背压能力的物理引擎。通过在 `__init__` 中注入 `ResourceManager` 并在调度循环中集成资源检查、获取和释放的逻辑，我们实现了《架构白皮书》中定义的“资源势能”概念。

### 目标
1.  更新 `Reactor` 的构造函数以接受 `ResourceManager`。
2.  在调度循环 (`step`) 中，增加资源可用性检查。
3.  实现一个等待队列 (`_pending_on_resource`) 来管理因资源不足而被阻塞的任务。
4.  在任务执行完毕后，释放其占用的资源，并唤醒等待队列中的任务进行重新评估。

### 基本原理
我们将重写 `Reactor` 的核心调度逻辑。
-   **资源检查**: 在激发一个数据就绪的 `FuncNode` 之前，会调用 `resource_manager.can_acquire()`。如果失败，节点会被移至 `_pending_on_resource` 集合。
-   **资源生命周期**: 在 `_fire` 方法中，我们首先调用 `await resource_manager.acquire()`，并将任务的需求记录下来。在 `_handle_execution_finished` 中，我们根据记录的需求调用 `await resource_manager.release()`。
-   **唤醒机制**: 资源释放后，`_pending_on_resource` 集合中的所有节点都会被移回 `_dirty_func_nodes`，以便在下一个 `step` 循环中被重新评估其执行条件。这确保了系统的响应性。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重写 Reactor 核心实现

由于改动幅度较大，涉及结构性变更，我们使用 `write_file` 策略来确保代码的完整性和清晰性。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python
import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any, Optional

from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel


class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[Any] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set()
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # State Sets
        self._dirty_func_nodes: Set[FuncNode] = set()
        self._pending_on_resource: Set[FuncNode] = set()
        self._in_flight_reqs: Dict[FuncNode, Dict[str, Any]] = {}

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        if isinstance(node, FuncNode):
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)
            
            for port_name, port in node.outputs.items():
                if port.target:
                    existing = any(
                        c.output_name == port_name and c.match("default")
                        for c in self._channels_by_source.get(node.name, [])
                    )
                    if not existing:
                        default_channel = Channel(
                            source=node,
                            target=port.target,
                            output_name=port_name,
                            tag_filter="default"
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        self._event_queue.append(event)

    async def step(self):
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            await self._handle_event(event)

        # 2. Evaluate Potentials
        # Move pending nodes back to dirty set for re-evaluation (Wake-up)
        self._dirty_func_nodes.update(self._pending_on_resource)
        self._pending_on_resource.clear()

        ready_to_fire = []
        still_dirty = set()

        for node in self._dirty_func_nodes:
            if not node.is_ready():
                still_dirty.add(node)
                continue

            # Resource Check
            requirements = getattr(node, 'resource_requirements', {})
            if self.resource_manager and not self.resource_manager.can_acquire(requirements):
                self._pending_on_resource.add(node)
            else:
                ready_to_fire.append((node, requirements))
        
        self._dirty_func_nodes = still_dirty
        
        # 3. Fire Ready Nodes
        if ready_to_fire:
            fire_tasks = [self._fire(node, reqs) for node, reqs in ready_to_fire]
            await asyncio.gather(*fire_tasks)

    async def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        event.node.put(event.token)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources, which implicitly triggers wake-up on next step
        if self.resource_manager and event.node in self._in_flight_reqs:
            requirements = self._in_flight_reqs.pop(event.node)
            await self.resource_manager.release(requirements)

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        for output_name, token in event.outputs.items():
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    async def _fire(self, node: FuncNode, requirements: Dict[str, Any]):
        # 1. Acquire Resources
        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)
            self._in_flight_reqs[node] = requirements

        # 2. Atomically consume inputs
        inputs = node.consume_inputs()
        
        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

### 下一步建议
我们已经完成了 Phase 4.1 和 4.2 的核心实现。下一步是运行测试套件，确认 `test_reactor_resource_awareness.py` 中的两个测试用例现在都已通过，从而正式进入 **GREEN** 状态。

如果测试通过，我们就可以进入 **REFACTOR** 阶段，对新代码进行清理和文档完善，或者直接进入第五阶段。
