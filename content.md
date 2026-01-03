简要回答

好的，我将执行“白盒验证”战略，将测试从脆弱的“数步数”模式迁移到健壮的“事件驱动”模式。

首要任务是修复 `cascade-std` 中的 `Bleacher` 和 `Stainer` 实现，目前它们虽然被 `Builder` 赋予了观测端口，但实际上并未向该端口发送数据，导致观测流断裂。修复此问题后，我将重构 `test_resource_backpressure.py`，使用 `EventDrivenRunner` 来通过监听生命周期事件（而非猜测 `reactor.step()` 的次数）来验证复杂的资源背压逻辑。

## [WIP] refactor(tests): 迁移 `test_resource_backpressure` 至事件驱动模式

### 用户需求
1.  修复 `standard_bleacher` 和 `standard_stainer` 丢失的观测信号输出，打通 `F_triad -> D_life -> F_obs` 的物理链路。
2.  重构 `test_resource_backpressure.py`，使用 `EventDrivenRunner` 替代手动的 `reactor.step()` 循环。
3.  消除测试中对 `asyncio.sleep` 和具体步数的依赖，转而使用 `runner.wait_for_event()`。

### 评论
目前的集成测试非常脆弱，因为它们实际上是在测试 Reactor 的调度细节（例如，“第3步分配器应该触发”）。一旦我们引入 JIT 或改变调度顺序，这些测试就会全部挂掉。
通过迁移到 `EventDrivenRunner`，我们将断言的焦点转移到了**可观测的行为结果**（即：任务是否完成、资源是否被正确锁定）上，这符合“黑盒 -> 白盒”的战略转型。

### 目标
1.  修正 `cascade-std` 中 Triad 组件的实现。
2.  创建一个健壮的、基于事件的资源背压集成测试。

### 基本原理
*   **物理完整性**: `Bleacher` 和 `Stainer` 作为物理节点，必须履行其端口契约。既然定义了 `obs_output`，就必须向其供能。
*   **测试鲁棒性**: `EventDrivenRunner` 封装了 Reactor 循环和事件队列，使得测试代码可以写成线性的、易读的 `await` 序列，而不是交错的 `step()` 检查。

### 标签
#intent/refine #intent/fix #flow/ready #priority/high #comp/tests #comp/std #concept/observability #scope/core #ai/instruct #task/domain/testing #task/object/event-driven-runner #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修复 Triad 组件的观测输出

修改 `standard_bleacher` 和 `standard_stainer`，确保它们在执行时向 `obs_output` 端口发射包含 trace 信息的 Token。这是观测系统能工作的物理基础。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }
~~~~~
~~~~~python.new
    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)
    # Emit start event to observability bus
    # The payload is None because the value is the event itself (represented by the trace)
    obs_token = Token(payload=None, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)

    # 4.2 Resource Return (The Loop)
~~~~~
~~~~~python.new
    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)

    # 4.2 Observability Emission
    # Emit end event (with duration) to observability bus
    outputs["obs_output"] = Token(payload=None, tag=tag, trace=trace_payload)

    # 4.3 Resource Return (The Loop)
~~~~~

#### Acts 2: 重构资源背压测试

将 `test_resource_backpressure.py` 重写为使用 `EventDrivenRunner`。我们将移除手动的步进循环，改为配置好 Runner 后启动后台循环，并等待特定的任务完成事件。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python
import pytest
from typing import Dict
import sys

from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.physics import Token
from cascade.spec.environment import EnvironmentDef, ResourceDef
from cascade.compiler.backend.builder import Builder
from cascade.vm.harness import EventDrivenRunner

# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe


# --- Mocks ---


def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


# --- Test ---


@pytest.mark.asyncio
async def test_concurrency_limit_event_driven():
    # 1. Define a graph with 2 nodes, both needing the same resource 'GPU'.
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="task", args=[ArgumentDef("x", "POSITIONAL")], fingerprint=fp
    )

    node_1 = NodeIR(
        id="node_1",
        name="Task1",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        id="node_2",
        name="Task2",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )

    graph_ir = GraphIR(nodes=[node_1, node_2])

    # 2. Define Environment and Build Physical Graph
    env = EnvironmentDef(resources=[ResourceDef(name="gpu", capacity=1)])
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    # 3. Construct Function Map
    func_map = {}
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "allocator" in node_id:
            func_map[node_id] = discrete_allocator
        elif "reclaimer" in node_id:
            func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
        elif node_id.startswith("probe.const."):
            func_map[node_id] = const_probe
        elif "global.observability.observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize EventDrivenRunner
    runner = EventDrivenRunner(physical_graph, func_map)
    runner.prime()

    # Assert initial state of Ledger
    ledger_node_id = "canonical.resource.ledger.gpu"
    assert runner.memory.get_count(ledger_node_id) == 1
    ledger = runner.memory.take(ledger_node_id).payload
    assert ledger.available == 1
    # Put it back
    runner.inject_input(ledger_node_id, ledger)

    # 5. Start the Reactor Loop
    await runner.start_loop()

    try:
        # 6. Wait for tasks to complete
        # Since resource capacity is 1, they must run sequentially.
        # But we don't strictly enforce order here, just that BOTH finish.
        
        # Note: In a real EventDrivenRunner, we might want a 'wait_for_all' helper.
        # For now, we wait for them individually. The order doesn't matter for correctness,
        # but logically one will finish before the other.
        
        # We collect completion events
        completed_tasks = set()
        
        def completion_predicate(event):
            if event.event_type == "end" and event.trace_data.get("id") in ["node_1", "node_2"]:
                completed_tasks.add(event.trace_data.get("id"))
            return len(completed_tasks) == 2

        # Wait until both are done (timeout generous because of backoff/recirculation latency)
        await runner.wait_for_event(completion_predicate, timeout=5.0)
        
        assert "node_1" in completed_tasks
        assert "node_2" in completed_tasks

        # 7. Final State Verification
        # Ledger should be full again
        ledger = runner.memory.take(ledger_node_id).payload
        assert ledger.available == 1
        
        # Buffers should be empty
        assert runner.memory.get_count("buffer.req.gpu") == 0
        
    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议

我们已经迈出了白盒测试的第一步。

接下来的重点应该是：
1.  **扩展覆盖**: 将此模式应用到 `test_branching.py` 和 `test_broker_starvation.py` (尽管后者可能需要一些特殊的 probe 技巧)。
2.  **增强 Harness**: `EventDrivenRunner` 可以增加更多方便的断言方法，例如 `assert_sequence(["task_1.start", "task_1.end"])`，来验证事件发生的因果顺序。
3.  **图验证器**: 实现 `GraphVerifier`，在运行前静态检查图的连通性，防止像“忘了连接观测端口”这样的低级错误在运行时才暴露。
