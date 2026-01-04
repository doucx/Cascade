你说得对，我的疏忽导致了这些集成测试的失败。`Builder` 的返回值已经变更为 `Assembly` 对象，但我没有将这个变更完全同步到 `cascade-vm` 包中的测试用例。这些测试仍然错误地假设 `builder.build()` 直接返回 `BipartiteGraph`。

我将立即生成一个计划来修复这两个测试。

## [WIP] fix: 适配 cascade-vm 集成测试以处理 Assembly 返回值

### 用户需求

修复 `cascade-vm` 包中的 `test_concurrency_limit` 和 `test_source_node_is_triggered_by_pulse` 测试，解决因 `Builder` 返回 `Assembly` 对象而导致的 `AttributeError`。

### 错误分析

在之前的重构中，`Builder.build` 方法的返回类型从 `BipartiteGraph` 更改为了 `Assembly`。然而，位于 `packages/cascade-vm/tests/integration/` 的测试用例没有相应更新。它们接收了 `Assembly` 对象，却仍然试图直接访问 `.nodes` 属性，而该属性现在位于 `Assembly.graph` 内部，导致了 `AttributeError`。

### 评论

这是一个典型的因重构影响范围评估不全而导致的问题。修复这些高层级的集成测试至关重要，因为它们是验证编译器 (`cascade-compiler`) 和虚拟机 (`cascade-vm`) 之间核心契约的最后防线。完成此修复将使我们的 Phase 2 成果更加稳固。

### 目标

1.  修改 `packages/cascade-vm/tests/integration/test_resource_backpressure.py`，正确地从 `Assembly` 对象中解包出 `BipartiteGraph`。
2.  修改 `packages/cascade-vm/tests/integration/test_source_node_execution.py`，执行同样的操作。

### 基本原理

解决方案很简单：在调用 `builder.build()` 后，将返回的 `Assembly` 对象赋值给一个新变量（如 `assembly`），然后从中提取 `.graph` 属性，再将其传递给后续需要 `BipartiteGraph` 对象的代码。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/vm #scope/core #ai/instruct #task/domain/compiler #task/object/linker-protocol #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 `test_resource_backpressure.py`

我们需要解包 `Assembly` 以获取图。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    # 3. Setup VM
    memory = VolatileMemory()
~~~~~
~~~~~python.new
    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    assembly = builder.build(graph_ir, environment=env)
    physical_graph = assembly.graph

    # 3. Setup VM
    memory = VolatileMemory()
~~~~~

#### Acts 2: 修复 `test_source_node_execution.py`

同样，在这里解包 `Assembly`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    physical_graph = builder.build(graph_ir, EnvironmentDef())

    # 2. Build the function map
    func_map = {}
~~~~~
~~~~~python.new
    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 2. Build the function map
    func_map = {}
~~~~~

### 下一步建议

这次的修复应该已经覆盖了所有已知的问题。请执行此计划，然后重新运行测试套件。如果一切顺利，我们就可以正式进入 **Phase 3**，开始实现 `CodeRegistry` 和 `Linker` 了。
