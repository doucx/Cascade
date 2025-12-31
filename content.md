好的，我们现在进入 Phase 4.2 的 GREEN 阶段。我们将实现 `run()` 方法，并引入 `asyncio.Event` 作为核心的等待/唤醒机制。

## [WIP] feat(vm): implement reactor run loop with wait/wake mechanism

### 用户需求
实现 `Reactor` 的 `run()` 方法，使其能够持续运行，并在没有任务时通过 `asyncio.Event` 挂起，直到新事件到达时被唤醒。

### 评论
这是将 `Reactor` 转化为一个真正独立的、自驱动的物理引擎的关键一步。`run()` 循环封装了 `step-wait-wake` 的核心逻辑，使 `Reactor` 能够在空闲时几乎不消耗 CPU，同时又能对新事件（如任务完成、资源释放）做出即时响应。`stop()` 方法则提供了优雅退出的能力。

### 目标
1.  向 `Reactor` 添加 `_is_running` 标志和 `_activity_signal` (`asyncio.Event`)。
2.  实现 `run()` 方法，包含主循环、调用 `step()` 和等待 `_activity_signal` 的逻辑。
3.  实现 `stop()` 方法，用于终止 `run()` 循环。
4.  修改 `push_event()`，使其在接收到新事件时设置 `_activity_signal` 以唤醒 `run()` 循环。

### 基本原理
`run()` 方法的核心是一个 `while self._is_running` 循环。在每次循环中，它首先调用 `await self.step()` 来处理所有当前可用的工作。如果处理完后系统没有更多立即可做的工作（事件队列为空，没有待处理节点），`run()` 循环就会 `await self._activity_signal.wait()`，从而将控制权交还给 `asyncio` 事件循环并进入休眠。当任何组件（包括 `Reactor` 自身）调用 `push_event()` 时，`_activity_signal` 会被设置，立即唤醒 `run()` 循环开始新一轮的 `step()`。

### 标签
#intent/build #flow/draft #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/reactor #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Reactor 中实现 run/stop 循环

我们将对 `core.py` 进行一次集中的修改，添加 `run` 循环所需的所有组件。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
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
        
        # Run Control
        self._is_running = False
        self._activity_signal = asyncio.Event()

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
        """Pushes an event to the queue and wakes up the run loop if it's waiting."""
        self._event_queue.append(event)
        self._activity_signal.set()

    def _has_pending_work(self) -> bool:
        """Checks if there's any immediate work to be done."""
        return bool(self._event_queue or self._dirty_func_nodes or self._pending_on_resource)

    async def run(self):
        """Continuously runs the reactor loop until stop() is called."""
        self._is_running = True
        while self._is_running:
            await self.step()
            
            # If step() resulted in more immediate work, loop again without waiting.
            if self._has_pending_work():
                continue
            
            # If no more work, wait for a new event to arrive.
            await self._activity_signal.wait()
            self._activity_signal.clear()

    def stop(self):
        """Stops the reactor's run loop gracefully."""
        self._is_running = False
        self._activity_signal.set()
~~~~~

### 下一步建议
我们已经完成了 `run()` 循环的实现。现在，所有 `Reactor` 相关的测试都应该通过，包括 `test_run_loop_proactively_schedules_tasks`。

下一步，你可以运行整个 `cascade-vm` 的测试套件来确认所有功能都已恢复 GREEN 状态。如果全部通过，Phase 4 就完成了，我们可以准备进入 Phase 5。
