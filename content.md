好的，我将修改 `test_reactor.py` 中的测试用例，以使用我们刚刚创建的全局 `reactor_backend_factory` Fixture。

这将验证我们的测试基础设施是否正常工作，并为未来的多后端测试提供一个清晰的范例。

## [WIP] test(vm): Adapt reactor test to use global backend fixture

### 用户需求
修改一个现有的 VM 测试用例，使其使用新的全局 `reactor_backend_factory` Fixture 来注入 Reactor 实现。

### 评论
这是一个完美的收尾工作。通过实际应用新创建的全局 Fixture，我们不仅验证了该基础设施的正确性，还为团队提供了一个可供复制的“黄金标准”模式。现在，我们所有的集成测试都可以轻松地参数化，以在不同的后端引擎上运行，从而确保了 Cascade 核心行为的一致性。

### 目标
1.  修改 `packages/cascade-vm/tests/unit/test_reactor.py` 文件。
2.  将 `reactor_backend_factory` Fixture 注入到 `test_event_driven_ping_pong` 测试函数中。
3.  在实例化 `EventDrivenRunner` 时，将此 Fixture 传递给 `reactor_factory` 参数。

### 基本原理
我们之前对 `EventDrivenRunner` 的重构（任务 1.2）就是为了这一刻。通过其 `__init__` 方法中暴露的 `reactor_factory` 参数，我们可以无缝地将由 `conftest.py` 提供的、通过命令行选择的 Reactor 类注入进去。这展示了“接口硬化”和“测试基建改造”这两个阶段是如何协同工作的。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/parameterized-fixture #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 将全局 Fixture 应用于测试用例

我们将修改 `test_event_driven_ping_pong`，使其能够利用我们的新测试基础设施。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_event_driven_ping_pong():
    # 1. Topology with Observability
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={
            "result": PortDef("result", PortRole.DATA),
            "obs_output": PortDef(
                "obs_output", PortRole.OBSERVABILITY
            ),  # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    # Obs Infra
    d_life = PhysicsDataNode(
        id="global.observability.bus", name="Bus", capacity=sys.maxsize
    )
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, d_life, f_obs]}

    # Logic Wiring
    graph.channels.append(Channel(d1.id, "out", f1.id, "value"))
    graph.channels.append(Channel(f1.id, "result", d2.id, "in"))

    # Obs Wiring
    # F1 emits directly to Bus (Simulating a Bleacher/Stainer behavior roughly)
    graph.channels.append(Channel(f1.id, "obs_output", d_life.id, "in"))
    graph.channels.append(Channel(d_life.id, "out", f_obs.id, "event_token"))

    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"}),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,
    }

    # 2. Use Runner
    runner = EventDrivenRunner(graph, func_map)
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1"
            and e.trace_data.get("status") == "done"
        )
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_event_driven_ping_pong(reactor_backend_factory):
    # 1. Topology with Observability
    d1 = PhysicsDataNode(id="D1", name="Input")
    f1 = PhysicsFuncNode(
        id="F1",
        name="Increment",
        input_ports={"value": PortDef("value", PortRole.DATA)},
        output_ports={
            "result": PortDef("result", PortRole.DATA),
            "obs_output": PortDef(
                "obs_output", PortRole.OBSERVABILITY
            ),  # Added Obs port
        },
    )
    d2 = PhysicsDataNode(id="D2", name="Output")

    # Obs Infra
    d_life = PhysicsDataNode(
        id="global.observability.bus", name="Bus", capacity=sys.maxsize
    )
    f_obs = ObservabilityNode(
        id="global.observability.observer",
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
    )

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d1, f1, d2, d_life, f_obs]}

    # Logic Wiring
    graph.channels.append(Channel(d1.id, "out", f1.id, "value"))
    graph.channels.append(Channel(f1.id, "result", d2.id, "in"))

    # Obs Wiring
    # F1 emits directly to Bus (Simulating a Bleacher/Stainer behavior roughly)
    graph.channels.append(Channel(f1.id, "obs_output", d_life.id, "in"))
    graph.channels.append(Channel(d_life.id, "out", f_obs.id, "event_token"))

    # Function Map
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
        return {
            "result": Token(payload=val + 1),
            "obs_output": Token(payload=None, trace={"id": "F1", "status": "done"}),
        }

    func_map = {
        "F1": obs_enabled_logic,
        "global.observability.observer": standard_observer,
    }

    # 2. Use Runner, injecting the backend factory
    runner = EventDrivenRunner(
        graph, func_map, reactor_factory=reactor_backend_factory
    )
    runner.inject_input("D1", 10)

    # 3. Start & Wait
    await runner.start_loop()

    try:
        # We wait for the specific event proving F1 finished
        event = await runner.wait_for_event(
            lambda e: e.trace_data.get("id") == "F1"
            and e.trace_data.get("status") == "done"
        )
        assert event is not None

        # Verify physical side effect (Memory)
        assert runner.memory.get_count("D2") == 1
        assert runner.memory.take("D2").payload == 11

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议

我们已经完成了架构演进路线图的前三个阶段：
1.  **接口硬化** (完成)
2.  **数据纯化** (完成)
3.  **测试基建改造** (完成)

现在，我们已经为 Rust VM 的“着陆”清理好了跑道，并准备好了验证其正确性的测试基础设施。

是时候进入**第四阶段：Rust 项目脚手架 (The Rust Bridgehead)** 了。这包括：
1.  **任务 4.1**: 在 `packages/` 目录下初始化一个名为 `cascade-vm-rs` 的新 Cargo 项目，并配置 `pyproject.toml` 以使用 Maturin 进行构建。
2.  **任务 4.2**: 实现一个“Hello World”级别的 Rust Reactor，它仅满足 `ReactorProtocol` 的接口契约，但内部逻辑为空。

如果你同意，我将生成一个计划来执行**任务 4.1**，为我们的 Rust 之旅奠定基础。
