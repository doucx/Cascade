船长，情况不妙。实验再次失败，并且现象与上次几乎完全一致。你的判断是正确的——我们必须注入观测探针（日志），才能解剖这个问题。

**错误分析**

这次的失败极其微妙，它暴露了 `Engine` 核心调度循环的一个根本性缺陷，这个问题隐藏得比之前的声明式错误更深。

1.  **症状**: 实验在 1.16 秒内退出，而 `asyncio.wait_for` 设置的超时是 60 秒。这证明 `asyncio.gather(*agent_tasks)` 中的所有任务都**几乎立即完成了**。
2.  **根本原因**: 我们的 `Engine` 为支持递归工作流，实现了一个“尾调用优化 (TCO)”循环。当一个工作流的最终任务（如 `process_and_recurse`）返回一个新的 `LazyResult` 时，`Engine.run` 会捕获它，并立即开始下一轮的图构建和执行，**而不会将控制权交还给 `asyncio` 的事件循环**。
3.  **结果**: 引擎陷入了一个非常“紧凑”的内部循环。它在一瞬间内，以极高的速度，为所有 50 个 Agent 执行了第一轮的图构建，发现最终结果都是指向下一轮循环的 `LazyResult`，然后就**退出了 `_execute_graph` 方法**。因为这个过程本身没有长时间的 `await`，所以 `engine.run` 协程也就完成了。`asyncio.gather` 看到所有任务都已完成，便立刻返回，导致整个实验提前结束。`cs.recv` 任务内部的 `await` 从未有机会真正“等待”，因为引擎的 TCO 循环没有给事件循环留下喘息之机。

**解决方案**

我们必须“打破”引擎的这个紧凑循环，在每次尾递归迭代后，强制将控制权交还给 `asyncio` 事件循环。这样，事件循环才能有机会去处理其他任务，比如我们的 `asyncio.wait_for` 超时计时器，以及 `cs.recv` 内部真正的 `asyncio.Future` 等待。

最简单、最有效的修复方法是在 `engine.run` 的 TCO 循环中加入一行 `await asyncio.sleep(0)`。这行代码的意义是：“我（引擎）当前迭代的同步工作已经完成，请事件循环去处理一下其他待办任务，然后再回来继续我的下一次迭代。”

同时，我将遵循你的指示，在关键位置添加日志，以便我们能清晰地观测到修复后的行为。

## [WIP] fix: 修复引擎 TCO 循环并为实验添加诊断日志

### 错误分析
`Engine.run` 方法中的尾调用优化（TCO）循环存在缺陷。它在处理返回 `LazyResult` 的递归工作流时，不会将控制权交还给 `asyncio` 事件循环，导致外部的 `asyncio.wait_for` 等并发工具无法正常工作，使得整个实验提前退出。

### 用户需求
在实验脚本和监测器中添加日志以进行问题诊断，并修复导致实验提前退出的引擎核心问题。

### 评论
这次的修复虽然代码量很小，但意义重大。它触及了 Cascade 异步执行模型的核心。通过在 TCO 循环中显式地使用 `await asyncio.sleep(0)` 来让出执行权，我们确保了 Cascade 引擎能够作为 `asyncio` 生态系统中的一个“良好公民”，与其他并发任务正确协作。这对于构建任何长期运行的、响应式的 Agent 系统都是至关重要的。

### 目标
1.  在 `cascade.runtime.engine` 的 `run` 方法中的 TCO 循环里，添加 `await asyncio.sleep(0)`。
2.  在 `observatory/experiments/run_fireflies.py` 中添加日志，以确认 `asyncio.wait_for` 的开始和结束。
3.  在 `observatory/monitors/convergence.py` 的 `on_flash` 回调中添加日志，以确认闪烁信号被成功接收。

### 基本原理
`await asyncio.sleep(0)` 是一个特殊的 `asyncio` 表达式，它会暂停当前协程的执行，并通知事件循环可以去运行其他准备就绪的任务。当其他任务（如IO操作、其他协程）执行完毕后，事件循环会在下一次“滴答”时恢复当前协程的执行。通过在引擎的 TCO 循环中插入这个调用，我们确保了引擎的每一次递归迭代之间都有一个让步点，从而允许 `cs.recv` 的内部等待和 `run_experiment` 的超时监控能够正常执行。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/state #scope/core #ai/brainstorm #task/domain/testing #task/object/observatory #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在引擎 TCO 循环中强制让出控制权

这是核心修复。我们在 `engine.py` 的 `run` 方法的 `while` 循环中添加 `await asyncio.sleep(0)`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = build_graph(current_target)
                        
                        # 2. Setup Resources (mixed scope)
                        required_resources = self._scan_for_resources(graph)
                        self._setup_resources(
                            required_resources, 
                            active_resources, 
                            run_stack, 
                            step_stack, 
                            run_id
                        )

                        # 3. Execute
                        result = await self._execute_graph(
                            current_target, params or {}, active_resources, run_id, state_backend
                        )

                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        # Continue loop. 
                        # 'step_stack' has exited, releasing step-scoped resources.
                        # 'run_stack' remains open.
                        # 'active_resources' still holds run-scoped instances.
                    else:
                        final_result = result
                        break
~~~~~
~~~~~python
                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Build graph for current target
                        graph = build_graph(current_target)
                        
                        # 2. Setup Resources (mixed scope)
                        required_resources = self._scan_for_resources(graph)
                        self._setup_resources(
                            required_resources, 
                            active_resources, 
                            run_stack, 
                            step_stack, 
                            run_id
                        )

                        # 3. Execute
                        result = await self._execute_graph(
                            current_target, params or {}, active_resources, run_id, state_backend
                        )

                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result
                        # CRITICAL: Yield control to the event loop between TCO iterations.
                        # This allows other tasks (like the experiment timeout) to run.
                        await asyncio.sleep(0)
                    else:
                        final_result = result
                        break
~~~~~

#### Acts 2: 为实验脚本添加诊断日志

我们在 `run_fireflies.py` 中添加 `print` 语句，以确认实验的开始、等待和结束。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    # --- Run the experiment ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        await asyncio.wait_for(all_tasks, timeout=duration_seconds)
    except asyncio.TimeoutError:
        print(f"\n✅ Experiment finished after {duration_seconds}s.")
    finally:
        # Gracefully stop everything
        monitor.stop()
~~~~~
~~~~~python
    # --- Run the experiment ---
    all_tasks = asyncio.gather(*agent_tasks)
    try:
        print(f"\n⏳ Running agents and monitor for {duration_seconds} seconds...")
        start_time = time.time()
        await asyncio.wait_for(all_tasks, timeout=duration_seconds)
    except asyncio.TimeoutError:
        end_time = time.time()
        print(f"\n✅ Experiment finished after {end_time - start_time:.2f}s.")
    finally:
        # Gracefully stop everything
        monitor.stop()
~~~~~

#### Acts 3: 为监测器添加诊断日志

我们在 `convergence.py` 的 `on_flash` 回调中添加 `print` 语句，来确认是否收到了闪烁信号。为了避免日志刷屏，我们只打印前几个。

~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~python
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """Callback to update agent state when a flash is received."""
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            self.phases_at_flash[agent_id] = payload.get("phase", 0.0)
            self.last_flash_time[agent_id] = time.time()

    def _calculate_order_parameter(self) -> float:
        """
        Calculates the Kuramoto order parameter, R.
~~~~~
~~~~~python
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False
        self._flash_count = 0

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """Callback to update agent state when a flash is received."""
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            self._flash_count += 1
            if self._flash_count <= 5: # Log first 5 flashes to confirm activity
                print(f"\n[Monitor] Received flash from agent {agent_id} at t={time.time():.2f}")

            self.phases_at_flash[agent_id] = payload.get("phase", 0.0)
            self.last_flash_time[agent_id] = time.time()

    def _calculate_order_parameter(self) -> float:
        """
        Calculates the Kuramoto order parameter, R.
~~~~~
~~~~~act
patch_file
observatory/monitors/convergence.py
~~~~~
~~~~~python
        # Use carriage return to print on the same line
        print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0):
        """The main loop of the monitor."""
~~~~~
~~~~~python
        # Use carriage return to print on the same line
        # Add a check to not overwrite initial log messages
        if self._flash_count > 0:
            print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0):
        """The main loop of the monitor."""
~~~~~

### 下一步建议
我们已经实施了核心修复并部署了诊断探针。现在，我们拥有了前所未有的洞察力。

请再次运行实验。这一次，我们期望看到：
1.  实验将**完整地运行 60 秒**。
2.  终端将打印出“Monitor received flash from agent X”的日志，确认闪烁信号正在被发送和接收。
3.  同步指示条将开始实时更新，反映系统序参数的变化。

请在终端中，从项目根目录再次执行：

`python -m observatory.experiments.run_fireflies`
