好的，分析完成。你的诊断非常精准，直指问题的核心。

**日志分析**: `flush_duration_ms` 高达 218ms, `render_jitter_ms` 达到 204ms，这清楚地表明 `asyncio` 事件循环被严重阻塞。渲染器本身并没有消耗这么多时间，而是它在等待获得 CPU 时间片。这印证了我们的怀疑：系统开销过大。

**核心问题**: 你完全正确，为 2500 个 Agent 分别创建 2500 个 `Engine` 实例是性能瓶颈的根源。
每个 `Engine` 实例都包含了自己的一整套重量级组件：`ResourceManager`、`ConstraintManager`、`MessageBus`、各种 `Handler` 和 `Resolver`。这造成了巨大的内存开销和 Python 对象管理开销，使得事件循环不堪重负。

**关于“共享上下文的生命周期灾难”**:
你对这个问题的警惕是正确的。之前的教训告诉我们，如果一个 `Engine` 的 `run` 方法附带了破坏共享资源的副作用（比如在 `finally` 中关闭一个共享的 `connector`），那么共享 `Engine` 实例是危险的。

**代码审查结论**:
经过对 `cascade-runtime` 核心代码的审查，我得出了关键结论：
1.  **状态隔离是安全的**: `Engine.run()` 在每次调用时都会通过 `state_backend_factory` 创建一个**全新的、独立的 `StateBackend` 实例**。这意味着不同工作流的执行结果、跳过状态等是完全隔离的。
2.  **资源作用域是安全的**: `ResourceManager` 的 `ExitStack` 机制确保了"run"作用域和"task"作用域的资源生命周期与**单次 `run()` 调用**绑定，而不是与 `Engine` 实例绑定。
3.  **发现了一个并发 BUG**: `Engine` 将 `flow_manager` 存储在 `self.flow_manager` 上。如果多个 `run()` 在同一个 `Engine` 实例上并发执行，它们会互相覆盖 `self.flow_manager`，造成数据竞争和未定义行为。

**解决方案**:
我们可以、也**必须**重构为共享 `Engine` 模式。但这需要先修复上述的并发 BUG。修复方案是将 `flow_manager` 从 `Engine` 的实例变量，降级为 `_execute_graph` 方法内部的一个局部变量。这样，每次 `run` 调用都会有自己独立的 `FlowManager`，从而实现真正的并发安全。

## [WIP] refactor(infra): Share a single Engine for all Firefly agents

### 用户需求
重构 `run_fireflies.py` 实验，使其使用单一的 `Engine` 实例来并发执行所有 2500 个 Agent 工作流，以解决性能瓶颈。

### 评论
这是一个根本性的架构优化。通过从“每个 Agent 一个重量级 Engine”模型迁移到“所有 Agent 共享一个 Engine，每个 Agent 是一个轻量级协程”的模型，我们将大幅降低系统开销，释放 `asyncio` 事件循环，从而让模拟流畅运行。

### 目标
1.  **修复** `Engine` 中的 `flow_manager` 并发安全问题。
2.  **重构** `run_fireflies.py`，在循环外创建唯一的 `Engine` 实例。
3.  在该 `Engine` 实例上并发启动所有 Agent 的 `run` 协程。

### 基本原理
`FlowManager` 的生命周期应与单次图的执行绑定，而不是 `Engine` 实例。通过将其变为 `_execute_graph` 的局部变量，我们消除了并发执行 `engine.run()` 时的数据竞争。修复此问题后，我们就可以安全地让所有 Agent 共享同一个 `Engine` 的资源管理和调度基础设施，同时保持它们各自执行状态的隔离。

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/runtime #concept/concurrency #scope/core #ai/brainstorm
#task/domain/infra
#task/object/engine-concurrency
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 修复 Engine 的并发安全问题

我们将 `flow_manager` 变为局部变量，以消除并发运行时的竞争条件。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
~~~~~
~~~~~python
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
    ) -> Any:
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
    ) -> Any:
        graph = build_graph(target)
        flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        # Track blocked state locally to avoid spamming Blocked events every loop tick
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if self.flow_manager:
                            self.flow_manager.register_result(
                                node.id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
~~~~~
~~~~~python
                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        flow_manager.register_result(
                            node.id, res, state_backend
                        )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
~~~~~

#### Acts 2: 重构实验脚本以使用共享 Engine

现在 `Engine` 是并发安全的了，我们可以放心地重构实验脚本。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    # --- Create Agents ---
    agent_tasks = []

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None,
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=connector,
            refractory_period=period * 0.2,
        )

        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)
~~~~~
~~~~~python
    # --- Create Shared Engine ---
    print("Initializing Shared Cascade Engine...")
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(), # A silent bus for the engine itself
        connector=None,
    )

    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector
    engine.register(shared_connector_provider)


    # --- Create Agents ---
    agent_tasks = []
    # Batch creation to avoid freezing UI loop
    print("Generating Agent Workflows...")
    for i in range(num_agents):
        initial_phase = random.uniform(0, period)

        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=cs.inject("_internal_connector"),
            refractory_period=period * 0.2,
        )

        # Schedule the workflow to run on the shared engine
        agent_tasks.append(engine.run(agent_workflow))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
            print(f"   ... {i} agents prepared.")
            await asyncio.sleep(0)
~~~~~

### 下一步建议
再次运行 `python -m observatory.experiments.run_fireflies`。我们预期会看到 `flush_duration_ms` 和 `render_jitter_ms` 大幅下降，模拟运行会变得非常流畅。如果成功，`INFRA-1.1` 和 `INFRA-1.2` 任务将正式完成。
