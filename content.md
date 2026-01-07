好的，我们来重构集成测试，消除外部停止器，实现一个能够自我终结的图，从而让测试更加真实和健壮。

## [WIP] test(vm): 重构集成测试以验证自终结工作流

### 用户需求
*   **债务**: 在 `test_machine_integration.py` 中，我们创建了一个并行的 `observer_task` 来监视输出节点并从外部停止 `Reactor`。
*   **影响**: 这使得测试逻辑与被测系统逻辑分离。测试本身没有验证一个“自停止”的图。
*   **偿还路径**: 重构测试图，使其包含一个完整的控制流路径。例如，将 `d_out` 连接到一个 `F_halt` 节点，从而让图在计算完成后，通过其自身的物理拓扑来发出 `HALT` 信号，实现自我终结。

### 评论
这次重构是“吃自己的狗粮 (Dogfooding)”原则的体现。我们不再用外部脚本来模拟工作流的结束，而是让工作流本身通过其拓扑结构来声明其生命周期的终点。这不仅使测试更真实地反映了系统的能力，还极大地简化了测试代码，用 `EventDrivenRunner` 这个高级测试工具取代了大量手动的底层组件设置。

### 目标
1.  修改 `test_machine_integration.py` 中的 `build_test_graph` 函数，在图的末端添加一个 `F_halt` 节点，并将最终输出数据节点连接到它。
2.  将测试逻辑从手动设置 `Machine`, `Reactor`, `LocalComputeService` 等组件，重构为使用 `EventDrivenRunner` 测试工具。
3.  移除外部的 `observer_task` 停止逻辑。
4.  修改测试断言，使其等待 `Machine` 任务 (`runner._loop_task`) 自然结束，然后检查 `EventDrivenRunner` 捕获的事件以验证计算结果。

### 基本原理
通过将 `d_out -> F_halt` 这条边添加到物理图中，我们创建了一个因果链：
1.  `square` 任务完成，其结果 Token 被放入 `d_out`。
2.  `d_out` 中的 Token 激活 `F_halt` 节点。
3.  `F_halt` 节点执行 `halt_signal` 内核函数，生成一个 `SystemControlToken(HALT)`。
4.  `Reactor` 捕获此控制 Token，并设置 `shutdown_event`。
5.  `Machine` 的主循环检测到 `shutdown_event` 已设置，退出循环，任务结束。

整个过程由图的内在物理定律驱动，无需任何外部干预。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #comp/runtime #scope/dx #ai/instruct #task/domain/runtime #task/object/self-termination #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `test_machine_integration.py`

由于改动幅度较大，涉及测试理念的根本转变，我们将使用 `write_file` 彻底重写此测试文件。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python
import asyncio
import pytest
from typing import Dict, Callable

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard Library ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal


# --- Test Fixtures ---


# 1. A simple async user function to be executed by the ComputeService
async def user_square(n: int) -> int:
    await asyncio.sleep(0.01)  # Simulate real async work
    return n * n


# 2. A helper to build the self-terminating physical graph for the test
def build_test_graph() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task_square"

    # Node IDs
    d_in_id = "d_in"
    d_out_id = "d_out"
    f_halt_id = "f_halt"
    f_bleach_id = PhysicalIdGenerator.bleach_node(base_id)
    d_worker_in_id = PhysicalIdGenerator.worker_in_data(base_id)
    f_worker_id = PhysicalIdGenerator.worker_node(base_id)
    d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
    d_trace_id = PhysicalIdGenerator.trace_data(base_id)
    f_stain_id = PhysicalIdGenerator.stain_node(base_id)

    # Node Definitions
    nodes = [
        PhysicsDataNode(id=d_in_id, name="Input"),
        BleachNode(
            id=f_bleach_id,
            name="Bleach(square)",
            input_ports={"n": PortDef("n", PortRole.DATA)},
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA),
                "trace_output": PortDef("trace_output", PortRole.DATA),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
            },
        ),
        PhysicsDataNode(id=d_worker_in_id, name="In(square)"),
        WorkerNode(
            id=f_worker_id,
            name="Exec(square)",
            canonical_code_structure_hash="hash_for_user_square",
            input_ports={"worker_input": PortDef("worker_input", PortRole.DATA)},
            output_ports={"worker_result": PortDef("worker_result", PortRole.DATA)},
        ),
        PhysicsDataNode(id=d_worker_out_id, name="Out(square)"),
        PhysicsDataNode(id=d_trace_id, name="Trace(square)"),
        StainNode(
            id=f_stain_id,
            name="Stain(square)",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA),
                "trace_input": PortDef("trace_input", PortRole.DATA),
            },
            output_ports={"output_default": PortDef("output_default", PortRole.DATA)},
        ),
        PhysicsDataNode(id=d_out_id, name="FinalOutput"),
        PhysicsFuncNode(
            id=f_halt_id,
            name="Halt",
            input_ports={"in": PortDef("in", PortRole.DATA)},
            output_ports={"out": PortDef("out", PortRole.DATA)},
        ),
    ]
    for node in nodes:
        graph.nodes[node.id] = node

    # Channels
    graph.channels.extend(
        [
            Channel(d_in_id, "out", f_bleach_id, "n"),
            Channel(f_bleach_id, "worker_input", d_worker_in_id, "in"),
            Channel(d_worker_in_id, "out", f_worker_id, "worker_input"),
            Channel(f_worker_id, "worker_result", d_worker_out_id, "in"),
            Channel(d_worker_out_id, "out", f_stain_id, "worker_result"),
            Channel(f_bleach_id, "trace_output", d_trace_id, "in"),
            Channel(d_trace_id, "out", f_stain_id, "trace_input"),
            Channel(f_stain_id, "output_default", d_out_id, "in"),
            # Add the self-termination channel
            Channel(d_out_id, "out", f_halt_id, "in"),
        ]
    )
    return graph


# --- The Test ---


@pytest.mark.asyncio
async def test_machine_runs_self_terminating_flow():
    # 1. Setup
    graph = build_test_graph()

    # Kernel Function Map (Standard Library ICs)
    function_map: Dict[str, Callable] = {
        PhysicalIdGenerator.bleach_node("task_square"): standard_bleacher,
        PhysicalIdGenerator.worker_node("task_square"): standard_dispatcher,
        PhysicalIdGenerator.stain_node("task_square"): standard_stainer,
        "f_halt": halt_signal,
    }

    # Code Registry (User Functions)
    code_registry = CodeRegistry()
    code_registry.register("hash_for_user_square", user_square)

    # Use the test harness for setup
    runner = EventDrivenRunner(graph, function_map, code_registry)

    # 2. Prime and Execute
    runner.inject_input("d_in", 10)
    await runner.start_loop()

    try:
        # 3. Wait for the machine to terminate on its own
        await asyncio.wait_for(runner._loop_task, timeout=5.0)

        # 4. Assert: Verify the final state by inspecting captured events
        # Find the completion event for our task
        completion_event = next(
            (
                e
                for e in runner._captured_events
                if isinstance(e, TaskExecutionFinished) and e.task_id == "task_square"
            ),
            None,
        )

        assert completion_event is not None, "Task completion event was not captured"
        assert (
            completion_event.status == "Succeeded"
        ), "Task did not succeed"

        final_ref = completion_event.result_preview
        final_result = runner.object_store.get(final_ref)

        assert final_result == 100, "The final result should be 10*10"
        print("Machine self-termination test passed: Final result is 100.")

    finally:
        # stop_loop is now just for cleanup, ensuring tasks are cancelled
        # if the test fails before self-termination.
        await runner.stop_loop()
~~~~~

### 下一步建议
我们已经完成了所有计划中的技术债务偿还工作，极大地增强了系统的健壮性、确定性和可维护性。

系统现在具备了：
-   真正的 `DRAIN` 优雅停机能力。
-   内核级的异常捕获和 `ERROR` 信号广播。
-   包含完整边界信息的 `CompilationManifest`。
-   高效、事件驱动的 `Machine` 主循环。
-   能够验证自终结工作流的、更真实的集成测试。

我们已经成功地用一批**可控的、明确的**技术债务替换了之前**不可控的、隐式的**架构缺陷。

下一步，我建议我们继续沿着增强架构完整性的道路前进，解决一个之前被推迟的功能：
*   **异常处理的“最后一公里”缺失**: `Stainer` 现在可以将异常路由到 `output_error` 端口，但我们没有提供任何标准的、内置的“错误处理”或“重试”物理节点来消费这个端口。

我提议将当前任务的目标变更为：**设计并实现一个标准的 `F_retry_logic` 物理节点**，使其能够消费 `output_error` 端口的输出，并实现基于次数的重试逻辑。
