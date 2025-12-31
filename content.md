简要回答：
好的，你的判断是正确的。盲目修复不如先增强可观测性。我将在 `Reactor.step()` 方法中插入一系列诊断日志，以精确追踪事件队列的状态、事件处理流程以及脏节点集的变化。这将明确告诉我们 `TokenGenerated` 事件是否被正确处理，或者在哪个环节被丢弃了。

## [WIP] fix: Add diagnostic logging to Reactor

### 用户需求
在 `Reactor` 的核心 `step` 方法中添加日志，以排查 `TokenGenerated` 事件未正确更新 `DataNode` 状态的根本原因。

### 评论
这是一个经典的调试场景。`AssertionError: assert None == Token(...)` 明确指出 `d_node.put(token)` 从未被执行。我们的日志记录策略将围绕这个核心假设展开，目的是验证事件处理流程的每一步是否都按预期执行。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py`。
2.  在 `Reactor.step` 方法中添加 `print()` 语句，以可视化事件队列、当前处理的事件以及脏节点集的状态。

### 基本原理
通过在关键逻辑点（进入 `step`、处理事件、处理后）打印状态，我们可以构建出事件流的完整轨迹。
- 如果日志显示事件队列为空，说明 `push_event` 可能有问题。
- 如果日志显示事件被处理，但没有进入 `_handle_token_generated` 的日志，说明 `isinstance` 判断失败。
- 如果所有日志都符合预期，但断言仍然失败，则可能存在对象引用问题（即测试中的 `d_node` 与 `Reactor` 中的 `event.node` 不是同一个对象）。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/executor #scope/dx #ai/instruct #task/domain/runtime #task/object/reactor #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在 `Reactor.step` 中注入日志记录

我们将使用 `patch_file` 来重写 `step` 方法，并加入详细的日志输出。

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
        # 1. Process Event Loop
        # We drain the queue completely to handle propagation chains within one step.
        while self._event_queue:
            event = self._event_queue.popleft()
            self._handle_event(event)

        # 2. Fire Ready Nodes
        # Iterate over a snapshot of dirty nodes
        ready_nodes = []
        for node in list(self._dirty_func_nodes):
            if node.is_ready():
                ready_nodes.append(node)
        
        self._dirty_func_nodes.clear()

        for node in ready_nodes:
            self._fire(node)

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
~~~~~

### 下一步建议
请再次运行测试。这次，测试输出中将包含详细的 `[REACTOR]` 日志。请将完整的失败输出（包括日志）提供给我，我将根据日志流分析出问题的确切位置。
