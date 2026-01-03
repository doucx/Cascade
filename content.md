## [WIP] refactor(std): 完成资源协商 IC 组件 (Requestor, Bleacher, Stainer)

### 用户需求
继续执行“Broker 归位”战略。
修正上一阶段设计中的逻辑缺陷（即“让 Bleacher 主动发起请求”导致的循环依赖问题）。
我们需要一组功能完备的 IC 组件，以便后续在 Builder 中组装出 $F_{req} \to F_{broker} \to F_{bleach}$ 的物理拓扑。

### 评论
在深入分析白皮书 5.2 节后，我们发现之前的设计（Bleacher 既是申请者也是等待者）在物理层是不可行的。
正确的物理模型应当是：
1.  **独立申请者 ($F_{req}$)**: 由 `Pulse` 激发，读取常量需求，打上 Tag (Task ID)，向 Broker 发起申请。
2.  **独立等待者 ($F_{bleach}$)**: 等待 Broker 发回的 GNT Token。
3.  **独立释放者 ($F_{stain}$)**: 任务结束后，根据申请量归还资源。

### 目标
1.  **新建** `cascade.std.resource.requestor`: 一个新的 IC，充当 Tag 注入器，将无状态的常量数值转换为带有路由 Tag 的 Request Token。
2.  **修正** `standard_bleacher`: 移除错误的 `RESOURCE_REQUEST` 逻辑。增加逻辑以记录 GNT Token 中的 payload (资源量) 到 Trace 中，供后续释放使用。
3.  **修正** `standard_stainer`: 增加逻辑，从 Trace 中读取资源量，并发射带有正确 Payload 的 Release Token。

### 基本原理
物理层的纯粹性要求每个节点职责单一。
*   `Requestor` 负责“身份注入” (Tagging)。
*   `Bleacher` 负责“状态同步” (Waiting & Tracing)。
*   `Stainer` 负责“状态清理” (Releasing)。
通过 Trace 通道 (`D_trace`) 传递资源数量，保证了 `Stainer` 能够正确归还借用的资源，实现了闭环的守恒。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/resource-ic #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Requestor IC

这是一个简单的转换器：Input(Amount) -> Output(Token with Tag)。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    """
    Acts as a Tag Injector.
    Takes a raw amount (from a Const Probe) and wraps it in a Token
    tagged with this node's ID (or a configured tag).

    In the Builder, we will map this node's ID to something that correlates
    with the Task ID, so the Broker can route the Grant back.
    """
    amount_token = inputs["amount"]
    
    # We use the node's own ID as the routing tag.
    # The Builder is responsible for ensuring the Distributor downstream
    # knows how to route 'node.id' back to the correct Bleacher.
    return {"req_out": Token(payload=amount_token.payload, tag=node.id)}
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/resource/requestor.stitcher.yaml
~~~~~
~~~~~yaml
"resource_requestor": |-
  Takes an input amount and emits a Request Token tagged with the node's ID.
  Used to initiate a resource transaction with a Broker.
~~~~~

#### Acts 2: 修正 Bleacher 逻辑

移除上一步添加的 `RESOURCE_REQUEST` 逻辑，改为记录资源数量。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
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
~~~~~python.new
        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a GNT token.
            # We record the port name as a held resource.
            held_resources.append(port_name)
            # CRITICAL: Record the granted amount (payload) to trace.
            # This allows the Stainer to know how much to release later.
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload
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

#### Acts 3: 修正 Stainer 逻辑

使其能够从 Trace 读取数量并释放。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 4.2 Resource Return (The Loop)
    # We iterate over the node's output ports to find all RESOURCE ports.
    # This is a static guarantee: if the node has a resource output port, we MUST emit to it.
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Emit a generic token to the resource port to "refill" the slot
            outputs[port_name] = Token(payload=None)

    return outputs
~~~~~
~~~~~python.new
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

#### Acts 4: 注册 Requestor 到 Init

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/__init__.py
~~~~~
~~~~~python.old
# Resource Broker ICs for managing physical resource constraints.
~~~~~
~~~~~python.new
# Resource Broker ICs for managing physical resource constraints.
from .requestor import resource_requestor

__all__ = ["resource_requestor"]
~~~~~

### 下一步建议
IC 层准备就绪。
下一步是 **Builder 改造 (The Grand Assembly)**：
1.  修改 `cascade-compiler/backend/builder.py`。
2.  实例化全局 `Broker` 节点 (Discrete/Continuous)。
3.  对于每个 Task 的每个资源约束：
    *   生成 $F_{probe}$ (Const) 提供数量。
    *   生成 $F_{req}$ (Requestor) 打 Tag。
    *   连接：$F_{probe} \to F_{req} \to F_{broker}$。
    *   连接：$F_{broker} \to F_{bleach}$ (通过 Channel Filter)。
    *   连接：$F_{stain} \to F_{broker}$。
这将彻底完成“Broker 归位”战略。
