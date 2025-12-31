好的，我们现在开始执行修复。根据分析，问题的核心在于 `VMExecutionStrategy` 与 `Reactor` 之间的交互模式：策略层必须**异步地**运行物理引擎，并**主动监听**目标结果的产生，而不是被动地等待一个永不结束的循环。

为了实现这一点，我们需要先增强 `Reactor`，使其能够向外界报告内部发生的事件（即“观察者模式”），然后更新策略层来利用这一机制。

## [WIP] fix(vm): 实现 Reactor 事件监听与 Strategy 异步执行

### 用户需求
修复 `VMExecutionStrategy` 中的死锁问题。当前代码错误地 `await` 了无限循环的 `reactor.run()`。

### 评论
通过引入“事件监听”机制，我们将解耦 `Reactor` 的运行循环与结果获取逻辑。`Reactor` 只负责跑物理模拟，`Strategy` 负责在旁边看着，一旦看到想要的结果（Token 落入目标 DataNode），就立马叫停 `Reactor` 并返回结果。这是一种更健壮、更符合物理引擎范式的设计。

### 目标
1.  **增强 Reactor**: 修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py`，添加 `add_listener` 方法，并在处理每个事件时通知所有监听器。
2.  **重构 Strategy**: 修改 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py`。不再阻塞等待 `reactor.run()`，而是将其放入后台任务。使用 `asyncio.Future` 配合新的监听器来捕获最终结果，并在获胜后优雅关闭 `Reactor`。

### 基本原理
事件驱动系统的控制流不能是线性的。控制者（Strategy）必须作为观察者存在，通过订阅特定事件（如“结果生成”）来驱动状态机的终止。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/vm #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 为 Reactor 添加事件监听能力

我们需要让外部能够“听到”反应堆内部发生的事情。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set()
~~~~~
~~~~~python.new
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        self._listeners: List[Any] = []
        
        # Topology Indexes
        self._nodes: Set[Any] = set()
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
~~~~~
~~~~~python.new
    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        self.register_node(channel.source)
        self.register_node(channel.target)

    def add_listener(self, callback):
        self._listeners.append(callback)

    def push_event(self, event: ReactorEvent):
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
~~~~~
~~~~~python.new
    async def _handle_event(self, event: ReactorEvent):
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                # Listeners should not break the reactor loop
                pass

        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
~~~~~

#### Acts 2: 重构 Strategy 以使用异步监听模式

现在我们将修改策略层，使用新的监听能力来非阻塞地获取结果。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # 8. Run
        await reactor.run()

        # 9. Extract Result
        if target_output_d_node and target_output_d_node.is_excited():
            return target_output_d_node.peek().payload
        
        return None
~~~~~
~~~~~python.new
        # 8. Run & Observe
        # We need to run the reactor in the background and wait for the result token
        # to appear in the target output node.
        
        result_future = asyncio.Future()

        def on_event(event):
            # Check if this event is the generation of our target result
            if isinstance(event, TokenGenerated) and event.node is target_output_d_node:
                if not result_future.done():
                    result_future.set_result(event.token.payload)

        reactor.add_listener(on_event)
        
        # Start Reactor in background
        reactor_task = asyncio.create_task(reactor.run())
        
        try:
            # Wait for the result (or exception propagation)
            # If target_output_d_node is None (e.g. void workflow), this logic needs refinement,
            # but for now we assume all valid workflows produce a result.
            if target_output_d_node:
                return await result_future
            else:
                # If no output is expected, we might just wait for reactor to idle?
                # But reactor.run() is infinite. 
                # For now, we assume value-returning tasks.
                # If we really need void support, we'd need an "Idle" event from Reactor.
                return None
        finally:
            # Cleanup: Stop reactor and await its shutdown
            reactor.stop()
            # We cancel/await to ensure no dangling tasks
            await reactor_task
~~~~~

### 下一步建议
我们已经完成了核心修复。现在，请重新运行我们的生命周期测试：
`pytest packages/cascade-engine/tests/integration/test_vm_strategy_lifecycle.py`

如果这个测试通过（变绿），那就意味着我们成功修复了死锁问题，打通了新架构的任督二脉。随后，我们可以回过头去运行那个被跳过的 TCO 测试 `test_vm_strategy_tco.py`，验证我们最初的目标。
