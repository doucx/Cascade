好的，我将生成一个 Quipu 计划，在 `_ReactorAdapter` 和 `Reactor` 的关键路径上插入诊断日志。这将帮助我们明确地追踪 `Jump` 信号的处理流程，并验证它是否如我们分析的那样被错误地处理了。

## [WIP] chore: 添加诊断日志以追踪 Jump 信号处理流程

### 用户需求
在 `VMExecutionStrategy` 和 `Reactor` 的相关部分插入日志代码，以诊断 TCO 测试中出现的死循环/死锁问题。

### 评论
这是一个标准的诊断步骤。通过将内部状态（如 `Jump` 对象的返回值、`Token` 的 `tag`、`Channel` 的 `tag_filter`）打印出来，我们可以将理论分析转化为可观测的证据，从而精确地定位问题根源。

### 目标
1.  在 `_ReactorAdapter._run_job` 中记录从 `Executor` 返回的原始结果，以及创建的 `Token` 的内容。
2.  在 `Reactor._handle_execution_finished` 中记录收到的 `Token` 及其 `tag`，并记录它尝试匹配的 `Channel` 的 `tag_filter`。

### 基本原理
我们怀疑 `cs.Jump` 对象没有被正确地翻译成带有相应 `tag` 的 `Token`，导致 `Reactor` 的路由逻辑失败，无法生成新的事件来驱动循环的下一次迭代。日志将验证这一假设。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/engine #concept/executor #scope/dx #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在 ReactorAdapter 中添加日志

我们将记录任务执行的直接返回值以及创建并发送给 `Reactor` 的 `Token`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
    async def _run_job(self, shim_node, args, kwargs, physics_node):
        try:
            result = await self.executor.execute(shim_node, args, kwargs)
            
            # 5. Pack Result (Default output port "result")
            # In the future, we might support multi-port output based on result type
            outputs = {"result": Token(payload=result)}
            
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, outputs=outputs)
            )
        except Exception as e:
            # Handle failure
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, error=e)
            )
~~~~~
~~~~~python.new
    async def _run_job(self, shim_node, args, kwargs, physics_node):
        try:
            result = await self.executor.execute(shim_node, args, kwargs)
            
            print(f"[DEBUG][Adapter] Task '{shim_node.name}' executed with result: {result!r}")

            # 5. Pack Result (Default output port "result")
            # In the future, we might support multi-port output based on result type
            outputs = {"result": Token(payload=result)}
            
            print(f"[DEBUG][Adapter] Pushing ExecutionFinished with outputs: {outputs!r}")
            
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, outputs=outputs)
            )
        except Exception as e:
            # Handle failure
            print(f"[DEBUG][Adapter] Task '{shim_node.name}' failed with error: {e}")
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, error=e)
            )
~~~~~

#### Acts 2: 在 Reactor 核心中添加日志

我们将记录 `Reactor` 在处理 `ExecutionFinished` 事件时的路由匹配逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources
        if self.resource_manager and event.node.resource_requirements:
            await self.resource_manager.release(event.node.resource_requirements)
            # Optimization hint: Releasing resources might wake up pending nodes.
            # In Phase 4.2, we might explicitly trigger a wake-up here.
            # For now, the next step() call will re-evaluate _pending_on_resource.

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        print(f"[DEBUG][Reactor] Handling ExecutionFinished for '{event.node.name}'. Found {len(channels)} outbound channels.")

        for output_name, token in event.outputs.items():
            print(f"[DEBUG][Reactor]  - Processing output '{output_name}' with token: {token!r}")
            routed = False
            # Find matching channels for this output port
            for channel in channels:
                print(f"[DEBUG][Reactor]    - Checking channel to '{channel.target.name}' with filter '{channel.tag_filter}'...")
                if channel.output_name == output_name and channel.match(token.tag):
                    print(f"[DEBUG][Reactor]      ✅ MATCH! Routing token.")
                    # Route: Generate a TokenGenerated event for the target DataNode
                    self.push_event(TokenGenerated(node=channel.target, token=token))
                    routed = True
            if not routed:
                print(f"[DEBUG][Reactor]    - ❌ NO MATCH found for token tag '{token.tag}' on port '{output_name}'. Token dropped.")
~~~~~

### 下一步建议
我们已经插入了详细的日志。现在，请再次运行 `pytest` 命令。由于测试会挂起，你可能需要再次手动按 `Ctrl+C` 来中断它，但这次我们应该能在 `stdout` 中看到详细的 `[DEBUG]` 日志，这将精确地揭示问题所在。
