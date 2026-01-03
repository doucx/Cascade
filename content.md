## [WIP] refactor(std): 增强 Broker 和 Bleacher 以支持物理资源协商

### 用户需求
为了实现符合白皮书 5.2 节定义的“物理资源协商闭环”，我们需要升级标准库中的集成电路 (IC) 实现：
1.  **Broker IC**: 必须支持基于 Tag 的路由，以便将资源授权 (Grant) 精确送回给发起请求的任务。
2.  **Bleacher IC**: 必须支持“主动请求”模式，即从输入端口读取“需求量”，并向输出端口发射携带身份 Tag 的“请求信标”。

### 评论
这是“Broker 归位”战略的第一步。我们首先确保底层的“物理器件”具备了必要的引脚和逻辑，然后才会在 Compiler 层重新组装它们。这种分层推进能降低风险。

### 目标
1.  修改 `discrete_broker` 和 `continuous_broker`，使其将 Request Token 的 `tag` 透传给 Grant Token。
2.  修改 `standard_bleacher`，使其能识别 `RESOURCE_REQUEST` 角色的输入，并自动向对应的输出端口发射携带 `tag=node.id` 的请求 Token。
3.  在 `PortName` 中添加必要的常量。

### 基本原理
*   **Tag 透传**: 在物理场中，Broker 是一个共享资源。为了支持多路复用，它必须像交换机一样工作，保留“源地址” (Tag)，以便下游的分配器 (Distributor) 能正确路由。
*   **Bleacher 的主动性**: 以前的 Bleacher 是被动的（等待资源）。现在的 Bleacher 是主动的（发起请求）。它需要读取一个常量输入（需求量），转化为一个动作（请求）。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #comp/spec #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/resource-broker #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新 Port 定义

我们需要明确定义用于资源请求量的端口角色。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ports.py
~~~~~
~~~~~python.old
class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"
~~~~~
~~~~~python.new
class PortRole(str, Enum):
    DATA = "DATA"
    RESOURCE = "RESOURCE"  # Legacy: Used for Stainer release
    RESOURCE_REQUEST = "RESOURCE_REQUEST"  # New: Used for Bleacher input (amount)
    SIGNAL = "SIGNAL"
    OBSERVABILITY = "OBSERVABILITY"
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ports.py
~~~~~
~~~~~python.old
class PortName:
    # Resources
    REQ = "req_in"
    REL = "rel_in"
    GNT = "gnt_out"
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"
~~~~~
~~~~~python.new
class PortName:
    # Resources
    REQ = "req_in"
    REL = "rel_in"
    GNT = "gnt_out"
    REQ_OUT = "req_out"  # For recirculation
    LEDGER_IN = "ledger_in"
    LEDGER_OUT = "ledger_out"
~~~~~

#### Acts 2: 增强 Discrete Broker

使其透传 Tag。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
        if ledger.available >= req_amount:
            # Grant
            ledger.available -= req_amount
            # Emit Grant Token (Payload can be the amount granted)
            outputs["gnt_out"] = Token(payload=req_amount)
        else:
            # Reject & Recirculate
            # We emit the original request token back to a recirculation loop
            outputs["req_out"] = req_token
~~~~~
~~~~~python.new
        if ledger.available >= req_amount:
            # Grant
            ledger.available -= req_amount
            # Emit Grant Token (Payload can be the amount granted)
            # CRITICAL: Propagate the tag from the request to the grant
            # so the distributor can route it back to the correct worker.
            outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
        else:
            # Reject & Recirculate
            # We emit the original request token back to a recirculation loop
            outputs["req_out"] = req_token
~~~~~

#### Acts 3: 增强 Continuous Broker

同样使其透传 Tag。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
        # Use a small epsilon for float comparison if needed, but >= usually suffices
        if ledger.available >= req_amount:
            ledger.available -= req_amount
            outputs["gnt_out"] = Token(payload=req_amount)
        else:
            # Recirculate
            outputs["req_out"] = req_token
~~~~~
~~~~~python.new
        # Use a small epsilon for float comparison if needed, but >= usually suffices
        if ledger.available >= req_amount:
            ledger.available -= req_amount
            # CRITICAL: Propagate the tag from the request to the grant
            outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
        else:
            # Recirculate
            outputs["req_out"] = req_token
~~~~~

#### Acts 4: 改造 Standard Bleacher

实现“读需求 -> 发请求”的转换逻辑。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a resource. We record it to trace.
            held_resources.append(port_name)
        # Observability and Signals are processed for trace but not passed to worker

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    trace_payload["start_ts"] = time.monotonic()
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }
~~~~~
~~~~~python.new
        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE_REQUEST:
            # New logic: This input defines a resource requirement amount.
            # We don't pass it to the worker, but we use it to emit a request token.
            # The 'port_name' here is expected to be something like 'req_amount_gpu'.
            # We need to map it to an output port.
            pass
        elif port_def.role == PortRole.RESOURCE:
            # Legacy/Fallback
            held_resources.append(port_name)

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    trace_payload["start_ts"] = time.monotonic()
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Create the output tokens
    outputs = {
        "worker_input": Token(payload=worker_payload),
        "trace_output": Token(payload=trace_payload),
    }

    # 4. Handle Active Resource Requests
    # We iterate over INPUT ports to find request amounts.
    # Convention: Input port 'req_amount_{res}' corresponds to Output port 'req_{res}'
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]
        if port_def.role == PortRole.RESOURCE_REQUEST:
            # Identify the resource name.
            # Assuming port name format: "req_amount_<resource_name>"
            if port_name.startswith("req_amount_"):
                res_name = port_name[11:]
                out_port_name = f"req_{res_name}"

                # Check if this output port exists
                if out_port_name in node.output_ports:
                    amount = input_token.payload
                    # Emit request token with tag = node.id (The Bleacher's ID)
                    # This allows the Grant to be routed back to the worker associated with this Bleacher.
                    # Note: We use the Bleacher's ID as the routing tag. The Distributor
                    # must route to the Worker based on this tag (or a derived one).
                    # Actually, let's use the Logical Node ID if possible.
                    # But node.id is physical (e.g. "node_1.bleach").
                    # Using "node_1.bleach" as tag is fine, as long as Builder knows this.
                    outputs[out_port_name] = Token(payload=amount, tag=node.id)

    return outputs
~~~~~

### 下一步建议
我们已经完成了底层 IC 的改造。
下一步，我们需要修改 `cascade-compiler/backend/expander.py`，更新它生成 Triad 的逻辑：
1.  Bleacher 不再有 `PortRole.RESOURCE` 输入，而是 `PortRole.RESOURCE_REQUEST` 输入（连接常量）和 `req_{name}` 输出。
2.  Worker 增加 `gnt_{name}` 输入（PortRole.RESOURCE）。
3.  Stainer 保持 `rel_{name}` 输出。
