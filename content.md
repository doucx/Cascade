好的，收到指令。立即停止行动，转入分析模式。

这是一个极好的、深度的捕获。测试的超时**不是一个随机的竞态条件**，而是暴露了我们标准库（`cascade-std`）中一个根本性的、潜伏至今的逻辑缺陷。你的测试用例像一个完美的探针，精确地触及了这个隐藏的断点。

**症状**:
测试在 `runner.wait_for_event(...)` 中超时。这意味着 `EventDrivenRunner` 的 `event_queue` 从未收到它所期望的“任务完成”事件。

**根本原因**:
要让一个“任务完成”事件出现在队列中，必须发生以下物理事件链：
1.  任务的 `StainNode` (`F_post`) 成功执行。
2.  `StainNode` 通过其 `obs_output` 端口，发射一个包含最终 `trace` 数据的 `Token`。
3.  这个 `Token` 流入全局的 `LifecycleBus` (`D_life`)。
4.  `LifecycleBus` 的 `Token` 激发 `LifecycleObserver` (`F_obs`)。
5.  `F_obs` 调用 `standard_observer` 函数。
6.  `standard_observer` 函数将一个 `ObservedEvent` 对象放入 `event_queue`。

通过仔细审查我们 `cascade-std` 库的实现，我发现这个链条在**第 2 步**就断了。

**缺陷定位**:
在 `packages/cascade-std/src/cascade/std/triad/stainer.py` 和 `bleacher.py` 文件中，`standard_stainer` 和 `standard_bleacher` 函数的实现存在缺陷。

*   **硬件 vs 软件**: `Expander` 在编译时，正确地为 `BleachNode` 和 `StainNode` 这两个“硬件”创建了 `obs_output` 物理端口。
*   **软件缺陷**: 但是，运行在这些节点上的“软件”——`standard_bleacher` 和 `standard_stainer` 函数——在它们的返回字典中，**从未包含 `"obs_output"` 这个键**。它们计算了所有需要的 `trace` 数据，但从未将这些数据打包成一个 `Token` 并从正确的端口发射出去。

因此，观测总线（`LifecycleBus`）从未收到任何 `start` 或 `end` 信号，`LifecycleObserver` 节点从未被激发，`event_queue` 始终为空，导致测试最终超时。

解决方案是修复 `cascade-std` 中的这两个核心函数，让它们正确地履行其与观测系统的契约。我将生成一个计划来修改 `standard_bleacher` 和 `standard_stainer`，确保它们在完成主要工作的同时，也通过 `obs_output` 端口发射一个带有完整 `trace` 数据的观测 `Token`。

这将修复事件链，使测试能够接收到预期的完成信号，从而通过。

---

现在，我将生成修复此问题的计划。

## [WIP] fix(std): 实现 bleacher 和 stainer 的观测令牌发射

### 错误分析
集成测试 `test_source_node_is_triggered_by_pulse` 因 `EventTimeoutError` 而失败。根本原因是 `cascade-std` 中的 `standard_bleacher` 和 `standard_stainer` 函数没有实现向其 `obs_output` 端口发射观测令牌的逻辑。尽管物理节点拥有该端口，但执行其逻辑的函数从未向其发送数据，导致观测系统从未收到任何 `start` 或 `end` 事件，队列始终为空，测试最终超时。

### 用户需求
修复 `standard_bleacher` 和 `standard_stainer` 的实现，使其能够正确地通过 `obs_output` 端口发射包含 `trace` 数据的观测令牌，从而修复超时的集成测试。

### 评论
这是一个关键的修复，它使我们的标准库实现与架构白皮书中定义的全息可观测性承诺完全对齐。通过修复这个缺陷，我们不仅能让测试通过，更重要的是，我们激活了整个系统的“神经系统”，使得未来所有基于此标准库构建的任务都将自动具备生命周期可观测性。

### 目标
1.  修改 `packages/cascade-std/src/cascade/std/triad/bleacher.py` 中的 `standard_bleacher` 函数，在返回字典中增加一个键为 `"obs_output"` 的 `Token`。
2.  修改 `packages/cascade-std/src/cascade/std/triad/stainer.py` 中的 `standard_stainer` 函数，在返回字典中增加一个键为 `"obs_output"` 的 `Token`。
3.  确保这两个 `Token` 的 `payload` 为 `None`（因为观测信号只关心元数据），但其 `trace` 属性包含了在该阶段计算出的完整 `trace_payload`。

### 基本原理
`BleachNode` 和 `StainNode` 是任务生命周期的起点和终点，它们分别拥有任务开始和结束时刻最完整的上下文信息。通过在其标准实现中增加向 `obs_output` 端口的输出，我们将这些关键的上下文信息（封装在 `trace` 中）广播到观测总线。这遵循了“旁路探测（Sidecar Probing）”的设计原则，即业务数据流与观测数据流分离，但共享相同的元数据。此修复将使这一原则在我们的标准库中得到正确实现。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #comp/std #task/domain/runtime #task/object/observability-emission #task/action/implementation #task-state/continue

---

### Script

#### Acts 1: 修复 Bleacher 和 Stainer

我们将依次修复这两个核心的标准库函数。

首先是 `standard_bleacher`：

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    # Pass the trace through to the worker so it can add to it
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }
~~~~~
~~~~~python.new
    # Pass the trace through to the worker so it can add to it
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    obs_token = Token(payload=None, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }
~~~~~

然后是 `standard_stainer`：

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)

    # 4.2 Resource Return (The Loop)
    # We iterate over the node's output ports to find all RESOURCE ports.
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Look up the amount to release from trace data
            # The Bleacher stored it under 'resource_amounts' -> 'res_{name}'
            # But the Stainer's output port might be named differently (e.g. 'rel_{name}' or just 'res_{name}')
            # Convention: If Stainer output is 'res_gpu', Bleacher input was 'res_gpu'.
            amount = 1  # Default fallback

            # Try to find the specific amount
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]

            # Emit token with the correct amount to replenish the broker
            outputs[port_name] = Token(payload=amount)

    return outputs
~~~~~
~~~~~python.new
    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)

    # 4.2 Observability Event
    outputs["obs_output"] = Token(payload=None, trace=trace_payload)

    # 4.3 Resource Return (The Loop)
    # We iterate over the node's output ports to find all RESOURCE ports.
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Look up the amount to release from trace data
            # The Bleacher stored it under 'resource_amounts' -> 'res_{name}'
            # But the Stainer's output port might be named differently (e.g. 'rel_{name}' or just 'res_{name}')
            # Convention: If Stainer output is 'res_gpu', Bleacher input was 'res_gpu'.
            amount = 1  # Default fallback

            # Try to find the specific amount
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]

            # Emit token with the correct amount to replenish the broker
            outputs[port_name] = Token(payload=amount)

    return outputs
~~~~~

### 下一步建议
我们已经定位并修复了标准库中的根本性缺陷。现在，`Bleacher` 和 `Stainer` 应该能正确发射观测事件了。

我建议立即重新运行 `test_source_node_is_triggered_by_pulse` 测试。如果它通过了，就证明我们的修复是成功的，并且整个从编译到执行再到观测的链路是完全通畅的。

在测试通过后，我们就可以自信地创建一个 `[COMMIT]` 计划来固化所有这些重构和修复工作。
