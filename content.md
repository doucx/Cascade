## [WIP] feat(vm): implement resource awareness in reactor

### 用户需求
实现 Phase 4.1 的目标：让 `Reactor` 感知并遵守 `ResourceManager` 的限制，防止任务过载。

### 评论
这是对物理引擎的核心增强。通过在调度循环中引入资源检查 (`can_acquire`) 和获取 (`acquire`) 逻辑，我们将 Reactor 从一个贪婪的调度器转变为一个受约束的物理引擎。

### 目标
1.  修改 `FuncNode` 以支持 `resource_requirements`。
2.  修改 `Reactor` 以注入 `ResourceManager`。
3.  在 `Reactor.step` 中实现资源门控逻辑。
4.  在 `Reactor` 事件处理中实现资源释放。

### 基本原理
我们采取“先检查再执行”的策略。在 `step` 循环中，对于每一个数据就绪 (`is_ready`) 的节点，我们首先检查系统资源是否充足。只有在资源充足时，我们才立即获取资源并提交任务。如果资源不足，该节点将被保留在待处理集合中（为 Phase 4.2 的等待唤醒机制做准备），从而避免了资源过载。

### 标签
#intent/build #flow/draft #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新 FuncNode 定义

首先，我们需要在物理层的 `FuncNode` 中添加资源需求的定义。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def __init__(self, name: str):
        self.name = name
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}

    def add_input(self, port: Port):
~~~~~
~~~~~python.new
    def __init__(
        self, 
        name: str, 
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}

    def add_input(self, port: Port):
~~~~~

#### Acts 2: 更新 Reactor 实现

接下来，我们重构 `Reactor` 核心。这包括：
1.  在 `__init__` 中接受 `ResourceManager`。
2.  在 `step` 中增加资源检查和获取逻辑。
3.  在 `ExecutionFinished` 处理中增加资源释放逻辑。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python
from typing import Optional
from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager


class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set() # Track all known nodes
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        
        # Optimization: Map DataNode -> List[FuncNode] (Reverse dependency)
        # Used to quickly find which FuncNodes to check when a DataNode updates.
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # Dirty set for potential evaluation
        self._dirty_func_nodes: Set[FuncNode] = set()
        
        # Pending set for nodes blocked by resources (Phase 4.2 foundation)
        self._pending_on_resource: Set[FuncNode] = set()

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes and Auto-discover Channels
        if isinstance(node, FuncNode):
            # 1. Reverse dependency map (DataNode -> Downstream FuncNodes)
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)
            
            # 2. Auto-discover Output Channels (Physics -> Routing)
            # If a port is connected to a DataNode physically, implies a default channel.
            for port_name, port in node.outputs.items():
                if port.target:
                    # Check if a channel already exists for this path to avoid duplicates
                    # or overriding explicit custom channels.
                    existing = any(
                        c.output_name == port_name and c.match("default")
                        for c in self._channels_by_source.get(node.name, [])
                    )
                    if not existing:
                        # Create implicit default channel
                        default_channel = Channel(
                            source=node,
                            target=port.target,
                            output_name=port_name,
                            tag_filter="default"
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        # Ensure nodes are registered
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        self._event_queue.append(event)

    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes (if resources allow).
        """
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            await self._handle_event(event)

        # 2. Evaluate Potentials
        # We process both new dirty nodes AND nodes previously pending on resources
        candidates = self._dirty_func_nodes.union(self._pending_on_resource)
        
        # Reset sets for this tick
        self._dirty_func_nodes.clear()
        self._pending_on_resource.clear()

        fire_tasks = []
        
        for node in candidates:
            if not node.is_ready():
                continue
                
            # Resource Check (Potential Barrier)
            if self.resource_manager and node.resource_requirements:
                if self.resource_manager.can_acquire(node.resource_requirements):
                    # Immediate acquisition to prevent over-commitment in this loop
                    # Note: can_acquire is synchronous, but acquire is async.
                    # Since we verified with can_acquire, acquire should not block significantly
                    # unless another process stole resources (unlikely in this single-threaded loop).
                    await self.resource_manager.acquire(node.resource_requirements)
                    fire_tasks.append(self._fire(node))
                else:
                    # Resource barrier not met, keep pending
                    self._pending_on_resource.add(node)
            else:
                # No resource constraints
                fire_tasks.append(self._fire(node))

        if fire_tasks:
            # Concurrently execute all fired nodes
            await asyncio.gather(*fire_tasks)

    async def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)
        
        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources
        if self.resource_manager and event.node.resource_requirements:
            await self.resource_manager.release(event.node.resource_requirements)
            # Optimization hint: Releasing resources might wake up pending nodes.
            # In Phase 4.2, we might explicitly trigger a wake-up here.
            # For now, the next step() call will re-evaluate _pending_on_resource.

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        await self.executor.submit(node, inputs)
~~~~~

### 下一步建议
我们已经实现了 Phase 4.1 的逻辑：`Reactor` 现在会检查资源并管理待处理节点。
这应该足以让 `test_reactor_respects_resource_concurrency_limit` 通过。
接下来的步骤：
1.  运行测试以验证 4.1 是否通过。
2.  如果不通过，进行调试和修复。
3.  如果 4.1 通过，`test_reactor_waits_for_resources_and_wakes_up` (Phase 4.2) 可能会失败，因为目前的实现依赖于外部再次调用 `step()` 来发现资源已释放。在 4.2 中，我们将实现更智能的唤醒机制。
