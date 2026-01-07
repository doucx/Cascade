好的，我们开始实施 `D_context` 通道。

根据我们的战略分析，这将为未来的重试机制奠定坚实的架构基础。我将生成一个计划，通过修改编译器后端和标准库，在“三连体”微观结构中加入这个新的旁路通道。

## [WIP] feat(core): Implement D_context side-channel for Triad retry capability

### 错误分析

无。此计划旨在实现一个新功能，解决一个先前诊断出的架构缺陷。

### 用户需求

在 Triad 物理结构中实现一个专用的 `D_context` 旁路通道。该通道的职责是持久化一个任务执行所需的完整输入上下文（输入引用），以便在任务失败时，下游的重试逻辑（如 `F_retry` 节点）可以使用此上下文重新触发任务。

### 评论

这是一个至关重要的架构演进。通过为重试上下文建立一个物理上独立的通道，我们遵循了“本体论正确性”原则，将“观测轨迹”（`D_trace`）和“执行上下文”（`D_context`）的职责清晰地分离开来。这不仅解决了当前输入信息丢失的问题，也为未来构建更复杂的、有状态的错误处理机制提供了无与伦比的清晰度和可扩展性。

### 目标

1.  在 `PhysicalIdGenerator` 中为新的上下文数据节点 (`D_context`) 添加一个规范的 ID 生成方法。
2.  修改编译器后端的 `Expander`，使其在为每个逻辑任务展开 Triad 子图时，自动创建 `D_context` 节点、在 `Bleacher` 和 `Stainer` 上创建相应的端口，并建立正确的内部连接。
3.  更新 `standard_bleacher` 的运行时逻辑，使其在处理输入后，将原始的输入引用（`input_refs`）打包成一个新的 `Token`，并从新增的 `context_output` 端口发出。
4.  更新 `standard_stainer` 的运行时逻辑，使其能够接收来自 `D_context` 的 `Token`，为未来的使用做好准备。

### 基本原理

我们将对系统的“创世”引擎（`Expander`）进行精确的外科手术。通过向 Triad 结构中注入一个新的 `PhysicsDataNode` (`D_context`) 和两条新的 `Channel`，我们建立了一条与主执行流和观测流并行的“上下文”流。`Bleacher` 将同时向 `D_worker_in`（用于立即执行）和 `D_context`（用于未来重试）发送相同的输入引用。`Stainer` 将消费 `D_context` 的内容，确保信息流的守恒。这个改动是纯粹的加法，对现有逻辑的侵入性极小，但极大地增强了系统的弹性和信息完整性。

### 标签

#intent/build #intent/architect #flow/ready #priority/high #comp/compiler #comp/engine #concept/state #scope/core #ai/delegate #task/domain/core #task/object/retry-context #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 `PhysicalIdGenerator`

首先，我们在 `cascade-reflection` 包中为 `D_context` 节点添加一个新的、规范的 ID 生成器方法。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
~~~~~
~~~~~python.new
    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
    def context_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.context"

    @staticmethod
~~~~~

#### Acts 2: 扩展 `Expander` 以构建 `D_context` 通道

接下来，修改 `cascade-compiler` 的核心 `Expander`。这是本次计划的核心，我们将在 Triad 中创建新的物理实体。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
        d_trace_id = PhysicalIdGenerator.trace_data(base_id)
        f_post_id = PhysicalIdGenerator.stain_node(base_id)

        # 2. Create Nodes
~~~~~
~~~~~python.new
        d_worker_out_id = PhysicalIdGenerator.worker_out_data(base_id)
        d_trace_id = PhysicalIdGenerator.trace_data(base_id)
        d_context_id = PhysicalIdGenerator.context_data(base_id)
        f_post_id = PhysicalIdGenerator.stain_node(base_id)

        # 2. Create Nodes
~~~~~
~~~~~python.old
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict"),
                "trace_output": PortDef("trace_output", PortRole.DATA, "TraceCtx"),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
            },
        )
~~~~~
~~~~~python.new
            output_ports={
                "worker_input": PortDef("worker_input", PortRole.DATA, "Dict"),
                "trace_output": PortDef("trace_output", PortRole.DATA, "TraceCtx"),
                "context_output": PortDef("context_output", PortRole.DATA, "Dict"),
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
            },
        )
~~~~~
~~~~~python.old
        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # F_post: The Stainer
~~~~~
~~~~~python.new
        # D_trace: The wormhole for metadata (start_ts, trace_id)
        d_trace = PhysicsDataNode(id=d_trace_id, name=f"Trace({node_ir.name})")

        # D_context: The wormhole for re-execution context (input refs)
        d_context = PhysicsDataNode(id=d_context_id, name=f"Context({node_ir.name})")

        # F_post: The Stainer
~~~~~
~~~~~python.old
        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any"),
                "trace_input": PortDef("trace_input", PortRole.DATA, "TraceCtx"),
            },
            output_ports=stainer_outputs,
        )
~~~~~
~~~~~python.new
        f_post = StainNode(
            id=f_post_id,
            name=f"Stain({node_ir.name})",
            input_ports={
                "worker_result": PortDef("worker_result", PortRole.DATA, "Any"),
                "trace_input": PortDef("trace_input", PortRole.DATA, "TraceCtx"),
                "context_input": PortDef("context_input", PortRole.DATA, "Dict"),
            },
            output_ports=stainer_outputs,
        )
~~~~~
~~~~~python.old
        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [f_pre, d_worker_in, f_worker, d_worker_out, d_trace, f_post]
        }
        subgraph.bleacher = f_pre
~~~~~
~~~~~python.new
        # Register nodes
        subgraph.nodes = {
            n.id: n
            for n in [
                f_pre,
                d_worker_in,
                f_worker,
                d_worker_out,
                d_trace,
                d_context,
                f_post,
            ]
        }
        subgraph.bleacher = f_pre
~~~~~
~~~~~python.old
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )

        subgraph.channels = channels
~~~~~
~~~~~python.new
        # D_trace -> F_post
        channels.append(
            Channel(
                source_node_id=d_trace_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="trace_input",
            )
        )

        # Path 3: Context Bypass
        # F_pre -> D_context
        channels.append(
            Channel(
                source_node_id=f_pre_id,
                source_port="context_output",
                target_node_id=d_context_id,
                target_port="in",
            )
        )
        # D_context -> F_post
        channels.append(
            Channel(
                source_node_id=d_context_id,
                source_port="out",
                target_node_id=f_post_id,
                target_port="context_input",
            )
        )

        subgraph.channels = channels
~~~~~

#### Acts 3: 更新 `standard_bleacher` 以填充 `D_context`

现在修改 `cascade-std` 中的 `standard_bleacher` 逻辑，使其生成并发出新的上下文 `Token`。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    # 4. Create the output tokens
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }
~~~~~
~~~~~python.new
    # 4. Create the output tokens
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    # The context payload IS the worker payload (the input refs)
    context_token = Token(payload=worker_payload, trace=trace_payload)
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "context_output": context_token,
        "obs_output": obs_token,
    }
~~~~~

#### Acts 4: 更新 `standard_stainer` 以消费 `D_context`

最后，修改 `standard_stainer` 以接收新的 `context_input`。目前我们只是简单地将其内容合并到最终的 `trace` 中，以确保信息守恒。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration
~~~~~
~~~~~python.new
    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]
    context_input_token = inputs.get("context_input")  # Use .get for graceful upgrade

    result_payload = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)
    if context_input_token:
        # For now, we just merge the context payload into the final trace,
        # under the key 'input_context'.
        trace_payload["input_context"] = context_input_token.payload

    # 2. Calculate duration
~~~~~

### 下一步建议

我们已经成功地在物理层面构建了信息守恒的旁路通道。现在，架构已经为真正的弹性做好了准备。

下一步的核心任务是：
1.  **实现 `F_retry` 物理节点**：创建一个新的标准库函数 (`standard_retry_logic`)，它可以被连接到 `Stainer` 的 `output_error` 端口。
2.  **消费上下文**：这个新的重试函数将消费来自 `D_error` 的错误 `Token` 和来自 `D_context` 的上下文 `Token`。
3.  **实现策略**：根据错误类型和重试次数（存储在 `D_context` 的 trace 中），决定是将原始输入 `Token` 重新注入到 `Bleacher`（实现重试），还是将其路由到一个永久失败的 `D_failed` 节点。

如果你同意，我将开始准备实现 `F_retry` 节点的计划。
