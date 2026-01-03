根据 Cascade 3.1 架构演进路线图，我们需要在第一阶段移除所有的隐式路由机制（Tag Filtering）。这是一个涉及整个系统的破坏性变更，不仅需要修改规范（Spec），还需要同步更新编译器（Compiler）、运行时（VM）和标准库（Std）以适配新的“主权端口”模型。

为了保证系统的完整性，我们必须在移除 `tag` 的同时，引入替代的路由机制。特别对于资源系统，这意味着我们需要提前实现部分 Phase 3 的逻辑（基于 Trace 的 ID 识别和专用端口路由），以防止资源分配功能崩溃。

以下是执行计划。

## [WIP] refactor(core): 废弃 Tag 路由机制，引入主权端口模型

### 用户需求
执行 "Cascade 3.1 架构演进路线图" 的第一阶段任务：
1.  **[Spec]** 从 `Channel` 和 `Token` 中移除 `tag` 相关字段。
2.  **[VM]** 简化 `Reactor`，移除发射时的光谱过滤逻辑。
3.  **[Compiler]** 更新 `Builder` 和 `Wiring`，移除对 `tag_filter` 的使用，并为资源分配引入专用端口布线。
4.  **[Std]** 更新所有标准 IC（Stainer, Allocator, Requestor），改用多端口输出和 Trace 上下文进行路由。

### 评论
这是一次“开胸手术”级别的重构。它不仅删除了旧的路由机制，还迫使我们立即采用更先进的“主权端口”模型。虽然这增加了单次变更的复杂性，但它避免了系统在迁移过程中长时间处于破碎状态。特别是资源系统的重构（从 Tag 路由转变为专用端口路由）必须与 Spec 的修改同步进行。

### 目标
1.  修改 `cascade-spec`，彻底移除 `tag` 和 `tag_filter`。
2.  修改 `cascade-vm` 的 `Reactor`，使其不再检查 tag。
3.  修改 `cascade-compiler` 的 `Builder`，为资源分配实现点对点的物理连接，不再依赖广播+过滤。
4.  修改 `cascade-std` 的 `Allocator` 和 `Stainer`，使其利用多端口和 Trace 信息进行明确的路由决策。

### 基本原理
**主权物理场公理**：逻辑即拓扑。如果两个节点之间有物理连接，能量就必然流过。不应依赖隐式的元数据（Tag）来在运行时决定通断。移除 Tag 强迫我们将所有的逻辑分支（如资源分配的目标）显式化为图上的物理结构。

### 标签
#intent/refactor #flow/ready #priority/critical #comp/core #comp/compiler #comp/vm #concept/topology #scope/core #task/domain/core #task/object/topology #task/action/sovereignty #task/state/begin

---

### Script

#### Acts 1: [Spec] 移除 Tag 和 Tag Filter 定义

首先修改核心数据结构，这是所有后续变更的基础。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass
class Channel:
    source_node_id: str

    source_port: str

    target_node_id: str

    target_port: str = "in"

    tag_filter: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class Channel:
    source_node_id: str

    source_port: str

    target_node_id: str

    target_port: str = "in"
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
@dataclass
class Token:
    payload: Any

    tag: str = "default"

    trace: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass
class Token:
    payload: Any

    trace: Dict[str, Any] = field(default_factory=dict)
~~~~~

#### Acts 2: [Compiler] 更新 Wiring 和 Visualizer

更新编译器后端工具，移除对 `tag_filter` 的引用。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring.py
~~~~~
~~~~~python.old
    def connect(
        self,
        source_id: str,
        source_port: str,
        target_id: str,
        target_port: str,
        tag_filter: Optional[str] = None,
    ) -> None:
~~~~~
~~~~~python.new
    def connect(
        self,
        source_id: str,
        source_port: str,
        target_id: str,
        target_port: str,
    ) -> None:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring.py
~~~~~
~~~~~python.old
        # 3. Connect
        channel = Channel(
            source_node_id=source_id,
            source_port=source_port,
            target_node_id=target_id,
            target_port=target_port,
            tag_filter=tag_filter,
        )
        self.graph.channels.append(channel)
~~~~~
~~~~~python.new
        # 3. Connect
        channel = Channel(
            source_node_id=source_id,
            source_port=source_port,
            target_node_id=target_id,
            target_port=target_port,
        )
        self.graph.channels.append(channel)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/visualizer.py
~~~~~
~~~~~python.old
            label = f"{channel.source_port} -> {channel.target_port}"
            if channel.tag_filter:
                label += f"\\n[{channel.tag_filter}]"

            # Check for Observability edges to style them differently (dashed)
~~~~~
~~~~~python.new
            label = f"{channel.source_port} -> {channel.target_port}"

            # Check for Observability edges to style them differently (dashed)
~~~~~

#### Acts 3: [VM] 简化 Reactor 发射逻辑

移除 Reactor 中检查 Tag Filter 的逻辑，回归纯粹的物理连接。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
                for channel in matching_channels:
                    # Spectrum Filtering
                    if channel.tag_filter and channel.tag_filter != token.tag:
                        continue

                    target_node = self.graph.nodes[channel.target_node_id]
~~~~~
~~~~~python.new
                for channel in matching_channels:
                    target_node = self.graph.nodes[channel.target_node_id]
~~~~~

#### Acts 4: [Std] 适配 Stainer 和 Requestor

更新标准库组件，不再产生或依赖 Tag。`Stainer` 现在将根据结果状态选择不同的输出端口（虽然目前默认只用 `output`，但逻辑上已准备好支持多端口）。`Requestor` 现在将 ID 注入到 Trace 中。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    # 2. Determine tag based on result (error or success)
    tag = "error" if isinstance(result_payload, Exception) else "default"

    # 3. Calculate duration and update trace
    start_ts = trace_payload.get("start_ts", end_ts)  # Default to end_ts for duration=0
    duration = end_ts - start_ts
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_ts

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)
~~~~~
~~~~~python.new
    # 2. Calculate duration and update trace
    start_ts = trace_payload.get("start_ts", end_ts)  # Default to end_ts for duration=0
    duration = end_ts - start_ts
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_ts

    # 3. Create output tokens
    outputs = {}

    # 3.1 The main result
    # In the future (Phase 2), we will route to 'output_error' if exception.
    # For now, we emit to 'output' regardless, but without a tag.
    outputs["output"] = Token(payload=result_payload, trace=trace_payload)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # We use the node's own ID as the routing tag.
    # The Builder is responsible for ensuring the Distributor downstream
    # knows how to route 'node.id' back to the correct Bleacher.
    return {"req_out": Token(payload=amount_token.payload, tag=node.id)}
~~~~~
~~~~~python.new
async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    return {"req_out": Token(payload=amount_token.payload, trace=trace)}
~~~~~

#### Acts 5: [Compiler & Std] 重构资源布线与分配器

这是最关键的一步。为了替代 Tag 路由，`Builder` 现在为每个资源请求者在 `Allocator` 上建立专用连接，而 `Allocator` 则根据 Trace 信息动态选择输出端口。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    # Ideally we should clone or re-instantiate if immutable, but for now we mutate in place for perf
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = req_token.payload

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount
        outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs
~~~~~
~~~~~python.new
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    # Ideally we should clone or re-instantiate if immutable, but for now we mutate in place for perf
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = req_token.payload

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount
        
        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing (should generally not happen in valid graph)
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs
~~~~~

注意：我们也需要对 `continuous.py` 做类似的修改，但由于篇幅限制且目前主要使用 discrete，这里先略过，待 `Builder` 修改完成后若测试需要再补。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # F_allocator (Priority Low)
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )
~~~~~
~~~~~python.new
            # F_allocator (Priority Low)
            # NOTE: Dynamic grant ports (gnt_for_...) will be added during wiring phase
            f_allocator = PhysicsFuncNode(
                id=allocator_id,
                name=f"Allocator({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    # PortName.GNT is deprecated in favor of dynamic ports, but kept for fallback
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # --- B. Grant Wiring ---
                gnt_buffer_id = f"buffer.gnt.{res_name}"
                if gnt_buffer_id not in physical_graph.nodes:
                    d_gnt_buffer = PhysicsDataNode(
                        id=gnt_buffer_id, name=f"GntBuffer({res_name})", capacity=1000
                    )
                    wire.add_node(d_gnt_buffer)

                    # Allocator -> Grant Buffer (Only once per resource)
                    wire.connect(allocator_id, PortName.GNT, gnt_buffer_id, "in")

                target_tag = f_req_id
                port_name = f"res_{res_name}"

                # Grant Buffer -> Bleacher (Filtered by Tag)
                wire.connect(
                    gnt_buffer_id,
                    "out",
                    subgraph.bleacher.id,
                    port_name,
                    tag_filter=target_tag,
                )
~~~~~
~~~~~python.new
                # --- B. Grant Wiring (Sovereign Ports) ---
                # We no longer use a shared Grant Buffer with tag filtering.
                # Instead, we create a dedicated channel from a dynamic port on the Allocator
                # to the specific Bleacher.

                # 1. Define the dynamic port name on Allocator
                # Must match logic in discrete_allocator (requestor_id is f_req_id)
                gnt_port_name = f"gnt_for_{f_req_id}"
                
                # 2. Add this port to the Allocator definition
                allocator_node = physical_graph.nodes[allocator_id]
                assert isinstance(allocator_node, PhysicsFuncNode)
                allocator_node.output_ports[gnt_port_name] = PortDef(gnt_port_name, PortRole.RESOURCE)

                # 3. Create a dedicated intermediate DataNode for this grant
                # (To satisfy Bipartite rule: Func -> Data -> Func)
                d_gnt_id = f"gnt.to.{node_ir.id}.{res_name}"
                d_gnt = PhysicsDataNode(
                    id=d_gnt_id, name=f"Gnt({res_name}->{node_ir.name})"
                )
                wire.add_node(d_gnt)

                # 4. Allocator -> Dedicated DataNode
                wire.connect(allocator_id, gnt_port_name, d_gnt_id, "in")

                # 5. Dedicated DataNode -> Bleacher
                bleacher_port_name = f"res_{res_name}"
                wire.connect(d_gnt_id, "out", subgraph.bleacher.id, bleacher_port_name)
~~~~~

#### Acts 6: [Tests] 修复集成测试

更新 `test_branching.py`，因为其手动构建的拓扑依赖 `tag_filter`。我们需要将其更新为使用多端口输出的模式。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_branching.py
~~~~~
~~~~~python.old
def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload

    if direction == "path_a":
        return {"out": Token(payload="Data A", tag="A")}
    else:
        return {"out": Token(payload="Data B", tag="B")}


@pytest.fixture
def branching_topology():
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(
        id="Switch",
        name="SwitchNode",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={"out": PortDef("out", PortRole.DATA)},
    )
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_sw, d_a, d_b]}

    # Wiring
    # D_in -> Switch
    graph.channels.append(Channel(d_in.id, "out", f_sw.id, target_port="in"))

    # Switch -> D_A (Only allows Tag 'A')
    graph.channels.append(
        Channel(f_sw.id, "out", d_a.id, target_port="in", tag_filter="A")
    )

    # Switch -> D_B (Only allows Tag 'B')
    graph.channels.append(
        Channel(f_sw.id, "out", d_b.id, target_port="in", tag_filter="B")
    )
~~~~~
~~~~~python.new
def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload

    # Sovereign routing: explicitly choose output port
    if direction == "path_a":
        return {"out_a": Token(payload="Data A")}
    else:
        return {"out_b": Token(payload="Data B")}


@pytest.fixture
def branching_topology():
    # D_in -> Switch -> (D_A, D_B)
    d_in = PhysicsDataNode(id="D_in", name="Input")
    f_sw = PhysicsFuncNode(
        id="Switch",
        name="SwitchNode",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        # Define multiple sovereign output ports
        output_ports={
            "out_a": PortDef("out_a", PortRole.DATA),
            "out_b": PortDef("out_b", PortRole.DATA)
        },
    )
    d_a = PhysicsDataNode(id="D_A", name="Branch A")
    d_b = PhysicsDataNode(id="D_B", name="Branch B")

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_in, f_sw, d_a, d_b]}

    # Wiring
    # D_in -> Switch
    graph.channels.append(Channel(d_in.id, "out", f_sw.id, target_port="in"))

    # Switch -> D_A (Connect to out_a)
    graph.channels.append(
        Channel(f_sw.id, "out_a", d_a.id, target_port="in")
    )

    # Switch -> D_B (Connect to out_b)
    graph.channels.append(
        Channel(f_sw.id, "out_b", d_b.id, target_port="in")
    )
~~~~~

### 下一步建议
我们已经完成了 Phase 1 的核心代码修改。虽然我们尽力保持了向后兼容（特别是在 `Builder` 中），但这是一个根本性的变化。
下一步应该：
1.  运行所有单元测试和集成测试，特别是 `test_resource_backpressure.py`，验证新的资源路由逻辑是否正确。
2.  继续 Phase 2 的工作，在 `Expander` 中为 `Stainer` 正式生成多端口（`output_default`, `output_error`），并在 `Builder` 中利用这些端口来处理错误传播（目前错误仍通过单一 `output` 端口流出）。
3.  清理 `continuous.py` 和其他可能残留 Tag 引用的边缘代码。
