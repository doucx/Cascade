好的，我们采纳调试驱动的开发策略。我将生成一个计划，在 E2E 测试中打印出编译后的物理图，以便我们能直观地诊断连接问题。

## [WIP] debug(vm): 在 E2E 测试中打印物理图以进行诊断

### 用户需求
修改 `test_e2e_vm_run.py` 测试，在 `Builder` 生成 `physical_graph` 后，将其结构（节点和通道）打印到 `stdout`。这将为我们提供诊断依赖关系是否正确建立的直接证据。

### 评论
这是一个关键的调试步骤，遵循“可观测性优先”的原则。通过将内存中的图结构物化为可读的文本，我们可以将一个复杂的运行时问题转换为一个静态的结构分析问题，从而能够精确地定位 `Builder` 中可能存在的布线错误。

### 目标
1.  修改 `packages/cascade-vm/tests/integration/test_e2e_vm_run.py`。
2.  在 `builder.build()` 调用之后，添加代码来遍历 `physical_graph.nodes` 和 `physical_graph.channels`。
3.  以清晰的格式打印出每个节点 ID 和名称，以及每个通道的 `source -> target` 连接关系。

### 基本原理
我们将利用 `pytest` 的 `stdout` 捕获功能。在测试执行期间，所有 `print` 语句的输出都会被捕获。当测试失败时，`pytest` 会将这些输出显示在失败报告中，从而为我们提供调试所需的上下文信息。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/compiler #scope/dx #ai/instruct #task/domain/testing #task/object/graph-visualization #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在测试中增加物理图打印逻辑

我们将 `patch` 测试文件，在编译后立即插入图的打印逻辑。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
    # Backend
    environment = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment)

    # 3. Manually set up the VM
    memory = VolatileMemory()
~~~~~
~~~~~python.new
    # Backend
    environment = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment)

    # --- DEBUG: Print Physical Graph ---
    print("\n--- [DEBUG] Physical Graph ---")
    print("Nodes:")
    for node_id, node in sorted(physical_graph.nodes.items()):
        print(f"  - {node_id} ({node.name})")
    print("\nChannels:")
    for channel in sorted(physical_graph.channels, key=lambda c: (c.source_node_id, c.target_node_id)):
        print(f"  - {channel.source_node_id}:{channel.source_port} -> {channel.target_node_id}:{channel.target_port}")
    print("----------------------------\n")
    # --- END DEBUG ---


    # 3. Manually set up the VM
    memory = VolatileMemory()
~~~~~

### 下一步建议
请运行 `pytest`。测试预计仍会因 `TimeoutError` 而失败，但这次的失败报告中将包含完整的物理图结构。请将包含 `--- [DEBUG] Physical Graph ---` 部分的 `stdout` 结果提供给我，我将基于这些确凿的证据进行最终的问题定位和修复。
