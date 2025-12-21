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
