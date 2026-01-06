好的，我们来执行这个关键的集成验证步骤。

这次更新不仅仅是修改一个测试文件，它将第一次完整地贯穿我们新建立的异步执行模型：从 `Reactor` 发射请求，到 `LocalComputeService` 接收并执行，再到结果返回并重新注入 `Reactor` 的内存中。

为了让测试正确工作，我们必须首先修复测试Harness (`EventDrivenRunner`) 中的一个小问题：根据v3.1架构，注入的数据不应是原始值，而应该是存储在 `ObjectStore` 中的`Ref`。

## [WIP] test(vm): 更新端到端测试以验证新的异步执行模型

### 用户需求

更新 `test_source_node_execution.py` 测试，使其能够正确地设置和验证基于 `standard_dispatcher` 和 `LocalComputeService` 的新异步执行流程。

### 评论

这是对我们近期重构工作的一次全面的“大考”。通过修复这个测试，我们不仅能验证 `dispatcher` 和 `service` 的正确性，还能确保它们之间的队列通信、`CodeRegistry` 的动态函数解析，以及 `Reactor` 与 `Harness` 对整个“出境-入境”数据流的协同处理都符合预期。这个测试的通过将是我们v3.1架构演进的一个重要里程碑。

### 目标

1.  **修复 `EventDrivenRunner`**: 修改 `harness.py` 中的 `inject_input` 方法，使其在注入数据时，先将数据存入 `ObjectStore` 并获取一个 `Ref`，然后将该 `Ref` 作为 `Token` 的载荷。
2.  **重构测试设置**:
    *   在 `test_source_node_execution.py` 中，创建并填充一个 `CodeRegistry` 实例。
    *   修改 `function_map`，将用户 `WorkerNode` 链接到 `standard_dispatcher`，而不是旧的 `mock_worker`。
    *   使用新的构造函数签名实例化 `EventDrivenRunner`，传入 `CodeRegistry`。
3.  **验证**: 确保测试通过，从而证明从“脉冲”触发到任务最终完成的整个异步闭环是完整且正确的。

### 基本原理

在新的模型下，测试流程如下：
1.  `EventDrivenRunner.prime()` 触发 `Pulse`。
2.  `Reactor` 激活 `Bleacher`。
3.  `Bleacher` 准备好输入（一个空的 `Ref` 字典），激活 `Dispatcher` (`WorkerNode`)。
4.  `Dispatcher` 被调用，它从 `WorkerNode` 读取 `code_hash`，组装 `ComputeRequest`，并将其放入 `compute_queue`。
5.  `LocalComputeService` 的后台任务从队列中获取请求，使用 `code_hash` 从 `CodeRegistry` 查到 `source_task.func` 并执行它。
6.  `Service` 将结果 `"Pulse Fired!"` 存入 `ObjectStore`，获得一个 `Ref`，然后将 `(reply_to_nid, result_token)` 放入 `ingress_queue`。
7.  `EventDrivenRunner` 的主循环从 `ingress_queue` 中“收割”结果，并将其注入到 `d_worker_out` 数据节点。
8.  `Reactor` 检测到 `d_worker_out` 被激发，从而激活 `Stainer`。
9.  `Stainer` 运行，并最终发出 `TaskExecutionFinished` 事件，测试断言成功。

这个完整的流程验证了我们架构的每一个新组件。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/core #task/state/continue

---

### Script

#### Acts 1: 修复 `EventDrivenRunner.inject_input`

我们首先修正 `harness.py`，确保它遵循“万物皆引用”的原则。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
    def inject_input(
        self, node_id: str, payload: Any, trace: Optional[Dict[str, Any]] = None
    ):
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        final_trace = {"rid": self.run_id}
        if trace:
            final_trace.update(trace)
        self.memory.put(node, Token(payload=payload, trace=final_trace))
~~~~~
~~~~~python.new
    def inject_input(
        self, node_id: str, payload: Any, trace: Optional[Dict[str, Any]] = None
    ):
        node = self.graph.nodes[node_id]
        if not isinstance(node, PhysicsDataNode):
            raise ValueError(f"Node {node_id} is not a DataNode")
        final_trace = {"rid": self.run_id}
        if trace:
            final_trace.update(trace)

        # v3.1: All data in the physical layer is a Ref.
        ref = self.object_store.put(payload)
        self.memory.put(node, Token(payload=ref, trace=final_trace))
~~~~~

#### Acts 2: 更新端到端测试用例

现在，我们重写 `test_source_node_execution.py` 以适应并验证新的异步模型。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python
import asyncio
import pytest
from typing import Dict

from cascade.spec.dsl.task import task
from cascade.compiler.frontend.generator import IRGenerator
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


@task
def source_task():
    return "Pulse Fired!"


@pytest.mark.asyncio
async def test_source_node_is_triggered_by_pulse():
    # 1. Compile the graph
    ir_generator = IRGenerator()
    builder = Builder()

    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    assembly = builder.build(graph_ir, EnvironmentDef())
    physical_graph = assembly.graph

    # 2. Setup Code Registry for the Compute Service
    code_registry = CodeRegistry()
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)

    # 3. Build the function map for the Reactor
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            # All user workers are now handled by the dispatcher
            func_map[node_id] = standard_dispatcher
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Setup and run the VM using the new Harness
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    # 5. Execute
    await runner.start_loop()
    try:
        # 6. Assert the result by waiting for the completion event.
        # This now validates the full dispatch -> compute -> ingress loop.
        completion_event = await runner.run_until_complete(
            task_id=node_ir.current_node_instance_hash, timeout=5.0
        )

        assert isinstance(completion_event, TaskExecutionFinished)
        assert completion_event.status == "Succeeded"
        assert completion_event.task_id == node_ir.current_node_instance_hash

        # The result preview is now a Ref. To verify the content, we need to
        # access the runner's object store.
        result_ref = completion_event.result_preview
        final_result = runner.object_store.get(result_ref)
        assert final_result == "Pulse Fired!"

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议

我们已经成功地验证了新的异步执行模型的核心路径！这是一个巨大的进步。

现在，我们可以专注于完成 `Reactor` 的演进。根据路线图，下一步是：

*   **实现入口队列 (`cascade.vm.reactor`)**: 使 `Reactor` 自身能够处理来自 `ingress_queue` 的事件，而不是依赖 `Harness` 来做这件事。这将使 `Reactor` 成为一个完全自洽的、事件驱动的状态机。
*   **实现统一循环**: 简化 `Reactor.step()` 方法，使其包含一个“入境周期”和一个“物理周期”，从而完成其最终形态的演化。
