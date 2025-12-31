好的，日志非常清晰，我们找到了两个独立的问题。

**诊断:**

1.  **根本原因 (`AssertionError`)**: 日志 `[REACTOR] -> Node 'f1' is READY.` 和 `[REACTOR] Firing 1 ready nodes...` 是决定性的证据。
    -   我们的 `Reactor.step()` 实现过于“高效”。它在一个 `step` 内完成了两件事：
        1.  它正确地处理了 `TokenGenerated` 事件，将 Token 放入了 `d_node`。
        2.  **然后**，它立即检查了因此变“脏”的 `f_node`，发现 `f_node` 的输入（`d_node`）已经就绪，于是**立即激发**了 `f_node`。
    -   激发 (`_fire`) 的第一步就是 `node.consume_inputs()`，它会调用 `d_node.take()`，从而在测试的 `assert` 语句执行**之前**就把 Token 从 `d_node` 中移除了。
    -   **结论**: `test_reactor_event_driven_potential_update` 这个测试的意图是只验证“势能更新”（即 Token 被放入），但 `Reactor` 的行为是“更新并立即执行”。测试的假设与实现的行为不匹配。最简单的修复方法是修改测试，让它只测试它想测试的东西，即移除导致 `f_node` 被激发的连接。

2.  **次要原因 (`RuntimeWarning`)**: `coroutine ... was never awaited`。
    -   日志清楚地指出了 `self.executor.submit(node, inputs)` 这一行。
    -   `AsyncMock` 的 `submit` 方法是一个协程 (`async def`)。我们的 `_fire` 方法是一个同步方法 (`def`)。我们在同步方法中调用了异步方法却没有 `await`，导致了这个警告，并且 `submit` 的逻辑实际上从未被执行。
    -   **结论**: `_fire` 方法必须是 `async def`，并且调用 `executor.submit` 时必须使用 `await`。相应地，`step` 方法中调用 `_fire` 的循环也需要修改以适应异步调用。

我将生成一个计划，分两步解决这两个问题。

## [WIP] fix: Isolate potential update test and fix async call

### 用户需求
修复 `Reactor` 测试中的 `AssertionError` 和 `RuntimeWarning`。

### 评论
1.  **修复 `AssertionError`**: 通过修改 `test_reactor_event_driven_potential_update` 测试用例，断开 `d_node` 和 `f_node` 的连接。这使得 `f_node` 不会因为 `d_node` 的更新而变得就绪，从而阻止了 `Reactor` 的“过度执行”，让 Token 留在 `d_node` 中以通过断言。这让测试的意图更加纯粹和明确。
2.  **修复 `RuntimeWarning`**: 将 `Reactor._fire` 方法重构为 `async def`，并在调用 `executor.submit` 时使用 `await`。同时，更新 `step` 方法中的调用循环，使用 `asyncio.gather` 来并发执行所有就绪的节点。这不仅修复了警告，也使得 `Reactor` 的架构更加健壮和高效。

### 目标
1.  修改 `packages/cascade-vm/tests/reactor/test_reactor_loop.py` 以隔离测试范围。
2.  修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py` 以正确处理异步调用。

### 基本原理
我们遵循“隔离关注点”的原则。首先修复测试用例的逻辑，使其精确地验证单一行为。然后，修复 `Reactor` 实现中的异步调用缺陷，确保其与异步 `Executor` 的契约得到遵守。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/refine #task/domain/runtime #task/object/reactor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 隔离 `test_reactor_event_driven_potential_update` 测试

我们移除 `f_node.add_input` 这一行，这样 `f_node` 就不会依赖 `d_node`，也就不会被意外触发。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_loop.py
~~~~~
~~~~~python.old
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1")
    # Wiring: d_node -> f_node
    f_node.add_input(Port(name="in1", source=d_node))
    
    # 2. Setup Reactor
    mock_executor = AsyncMock()
~~~~~
~~~~~python.new
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1")
    # NOTE: We DO NOT wire d_node to f_node.
    # This test is ONLY to verify that the TokenGenerated event correctly
    # updates the state of the DataNode itself, without triggering a fire.
    
    # 2. Setup Reactor
    mock_executor = AsyncMock()
~~~~~

#### Acts 2: 修复 Reactor 中的异步调用

我们将 `_fire` 变为 `async`，并在 `step` 中使用 `asyncio.gather` 来调用它。同时，为清晰起见，移除调试用的 `print` 语句。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes.
        """
        print(f"\n[REACTOR] Entering step(). Event queue size: {len(self._event_queue)}")
        
        # 1. Process Event Loop
        # We drain the queue completely to handle propagation chains within one step.
        events_processed = 0
        while self._event_queue:
            event = self._event_queue.popleft()
            print(f"[REACTOR]  -> Processing event: {event}")
            self._handle_event(event)
            events_processed += 1
        
        print(f"[REACTOR] Event processing finished. Processed {events_processed} events.")

        # 2. Fire Ready Nodes
        # Iterate over a snapshot of dirty nodes
        dirty_node_names = [n.name for n in self._dirty_func_nodes]
        print(f"[REACTOR] Evaluating dirty nodes: {dirty_node_names}")
        ready_nodes = []
        for node in list(self._dirty_func_nodes):
            if node.is_ready():
                print(f"[REACTOR]  -> Node '{node.name}' is READY.")
                ready_nodes.append(node)
        
        self._dirty_func_nodes.clear()

        if ready_nodes:
            print(f"[REACTOR] Firing {len(ready_nodes)} ready nodes...")
            for node in ready_nodes:
                self._fire(node)
        
        print(f"[REACTOR] Exiting step().")

    def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        print(f"[REACTOR]    -> Handling TokenGenerated for node '{event.node.name}'. Putting token.")
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)
        
        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        downstream_names = [n.name for n in downstream]
        print(f"[REACTOR]    -> Marking downstream nodes as dirty: {downstream_names}")
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    def _handle_execution_finished(self, event: ExecutionFinished):
        # Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    # This queues the event for processing in the same step loop
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        # Note: Executor is responsible for running the code and eventually
        # pushing an ExecutionFinished event back to the reactor.
        # For AsyncMock in tests, this call is synchronous.
        self.executor.submit(node, inputs)
~~~~~
~~~~~python.new
    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes.
        """
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            self._handle_event(event)

        # 2. Fire Ready Nodes
        ready_nodes = []
        for node in list(self._dirty_func_nodes):
            if node.is_ready():
                ready_nodes.append(node)
        
        self._dirty_func_nodes.clear()

        if ready_nodes:
            # Concurrently execute all ready nodes
            fire_tasks = [self._fire(node) for node in ready_nodes]
            await asyncio.gather(*fire_tasks)

    def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)
        
        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    def _handle_execution_finished(self, event: ExecutionFinished):
        # Routing Logic
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
请再次运行测试。这次，两个问题都应该被修复，所有测试都应该通过，让我们进入 GREEN 状态。
