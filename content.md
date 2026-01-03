## [WIP] refactor(core): 拆分 Broker 为 Allocator 和 Reclaimer 以解决死锁

### 用户需求
解决 `test_resource_backpressure.py` 中的测试失败。
根本原因是 Reactor 遵循“全输入激发 (Full-Input Firing)”原则，而原本的 broker 设计试图在一个节点上处理可选输入（Request 或 Release）。这导致 Broker 在没有 Release 输入时永远无法激发，从而死锁。
我们需要将 Broker 拆分为两个独立的物理实体：
1.  **Allocator**: 负责处理 Request，消耗 Ledger，产出 Grant。
2.  **Reclaimer**: 负责处理 Release，消耗 Ledger，归还资源。
二者通过竞争 `D_ledger` 中的唯一 Token 来实现序列化和状态共享。

### 评论
这是一个符合物理定律的架构修正。它消除了“可选输入”这一非物理概念，将其转化为对共享资源（Ledger）的竞争。

### 目标
1.  修改 `cascade-std` 中的 `discrete.py` 和 `continuous.py`，将 broker 函数拆分为 allocator 和 reclaimer。
2.  更新 `cascade-compiler` 的 `naming.py` 和 `builder.py` 以适配新结构。
3.  更新集成测试以使用新的函数映射。

### 基本原理
*   **Allocator**: Inputs: `{ledger_in, req_in}`, Outputs: `{ledger_out, gnt_out, req_out}`
*   **Reclaimer**: Inputs: `{ledger_in, rel_in}`, Outputs: `{ledger_out}`
*   **竞争模型**: `D_ledger` 充当互斥锁。Reactor 的顺序扫描保证了原子性。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #comp/compiler #comp/vm #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/broker #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 拆分 Discrete Broker IC

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
async def discrete_broker(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    # Reconstruct ledger object from payload (assuming it's a dict or dataclass)
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    outputs: Dict[str, Token] = {}

    # 1. Process Release (Replenish first)
    if "rel_in" in inputs:
        release_amount = inputs["rel_in"].payload
        # Cap at total to prevent overflow logic errors, though in a closed system this shouldn't happen
        ledger.available = min(ledger.total, ledger.available + release_amount)

    # 2. Process Request
    if "req_in" in inputs:
        req_token = inputs["req_in"]
        req_amount = req_token.payload

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

    # 3. Emit Updated Ledger
    # We pass the object back. In a real persistence scenario, this would be serialized.
    outputs["ledger_out"] = Token(payload=ledger)

    return outputs
~~~~~
~~~~~python.new
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    """
    Handles Resource Requests.
    Inputs: ledger_in, req_in
    Outputs: ledger_out, gnt_out (if success), req_out (if failed)
    """
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


async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    """
    Handles Resource Releases.
    Inputs: ledger_in, rel_in
    Outputs: ledger_out
    """
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = rel_token.payload

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.stitcher.yaml
~~~~~
~~~~~yaml.old
"discrete_broker": |-
  A Discrete Resource Broker using the Self-Loop Ledger pattern.

  Inputs:
      ledger_in: Token containing DiscreteLedger(total, available)
      req_in: (Optional) Token requesting N units. Payload: int
      rel_in: (Optional) Token releasing N units. Payload: int

  Outputs:
      ledger_out: Updated ledger
      gnt_out: (Conditional) Grant token if request succeeded
      req_out: (Conditional) Original request token if failed (Recirculation)
~~~~~
~~~~~yaml.new
"discrete_allocator": |-
  Handles allocation requests for discrete resources.
  Inputs: ledger_in, req_in
  Outputs: ledger_out, gnt_out (if granted), req_out (if rejected)

"discrete_reclaimer": |-
  Handles release (return) of discrete resources.
  Inputs: ledger_in, rel_in
  Outputs: ledger_out
~~~~~

#### Acts 2: 拆分 Continuous Broker IC

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
async def continuous_broker(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    outputs: Dict[str, Token] = {}

    # 1. Process Release
    if "rel_in" in inputs:
        release_amount = float(inputs["rel_in"].payload)
        # Simple clamp to avoid floating point drift exceeding total
        ledger.available = min(ledger.total, ledger.available + release_amount)

    # 2. Process Request
    if "req_in" in inputs:
        req_token = inputs["req_in"]
        req_amount = float(req_token.payload)

        # Use a small epsilon for float comparison if needed, but >= usually suffices
        if ledger.available >= req_amount:
            ledger.available -= req_amount
            # CRITICAL: Propagate the tag from the request to the grant
            outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
        else:
            # Recirculate
            outputs["req_out"] = req_token

    # 3. Emit Updated Ledger
    outputs["ledger_out"] = Token(payload=ledger)

    return outputs
~~~~~
~~~~~python.new
async def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = float(req_token.payload)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        ledger.available -= req_amount
        outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
    else:
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


async def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    release_amount = float(inputs["rel_in"].payload)
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}
~~~~~

#### Acts 3: 更新 Compiler Naming

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def global_broker(resource_name: str) -> str:
        return f"canonical.resource.broker.{resource_name}"
~~~~~
~~~~~python.new
    @staticmethod
    def global_allocator(resource_name: str) -> str:
        return f"canonical.resource.allocator.{resource_name}"

    @staticmethod
    def global_reclaimer(resource_name: str) -> str:
        return f"canonical.resource.reclaimer.{resource_name}"
~~~~~

#### Acts 4: 更新 Compiler Builder

重构 Builder 以生成两个独立的节点，共享同一个 Ledger。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 1. Create Resource Brokers (F_broker + internal Ledger loop)
        for res_def in environment.resources:
            broker_id = PhysicalIdGenerator.global_broker(res_def.name)
            ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

            # D_ledger: Holds the state of the resource
            # We initialize it with a DiscreteLedger object.
            # Currently we assume all resources are Discrete.
            # TODO: Support Continuous resources based on definition.
            initial_ledger = DiscreteLedger(
                total=res_def.capacity, available=res_def.capacity
            )

            d_ledger = PhysicsDataNode(
                id=ledger_id,
                name=f"Ledger({res_def.name})",
                capacity=1,
                initial_tokens=1,
                initial_payload=initial_ledger,
            )

            # F_broker: The logic unit
            f_broker = PhysicsFuncNode(
                id=broker_id,
                name=f"Broker({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )

            physical_graph.nodes[ledger_id] = d_ledger
            physical_graph.nodes[broker_id] = f_broker

            # Wire the Ledger Loop
            # D_ledger -> F_broker
            physical_graph.channels.append(
                Channel(
                    source_node_id=ledger_id,
                    source_port="out",
                    target_node_id=broker_id,
                    target_port=PortName.LEDGER_IN,
                )
            )
            # F_broker -> D_ledger
            physical_graph.channels.append(
                Channel(
                    source_node_id=broker_id,
                    source_port=PortName.LEDGER_OUT,
                    target_node_id=ledger_id,
                    target_port="in",
                )
            )

            # Self-Loop for Recirculation of rejected requests
            # If a request is rejected, it comes out of REQ_OUT and goes back to REQ_IN.
            # We need a buffer D_retry for this?
            # Or can we wire REQ_OUT -> D_req (which feeds REQ_IN)?
            # Yes, we will create a shared D_req_buffer for the broker later or handle it per request.
            # Actually, standard pattern is:
            # Inputs -> [D_req_buffer] -> F_broker
            # F_broker -> REQ_OUT -> [D_req_buffer]
            # Let's create a shared Request Buffer for this broker.
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )  # High capacity
            physical_graph.nodes[d_req_buffer_id] = d_req_buffer

            # Connect Buffer -> Broker
            physical_graph.channels.append(
                Channel(
                    source_node_id=d_req_buffer_id,
                    source_port="out",
                    target_node_id=broker_id,
                    target_port=PortName.REQ,
                )
            )

            # Connect Recirculation: Broker -> Buffer
            physical_graph.channels.append(
                Channel(
                    source_node_id=broker_id,
                    source_port=PortName.REQ_OUT,
                    target_node_id=d_req_buffer_id,
                    target_port="in",
                )
            )
~~~~~
~~~~~python.new
        # 1. Create Resource Brokers (Allocators + Reclaimers)
        for res_def in environment.resources:
            allocator_id = PhysicalIdGenerator.global_allocator(res_def.name)
            reclaimer_id = PhysicalIdGenerator.global_reclaimer(res_def.name)
            ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

            # D_ledger
            initial_ledger = DiscreteLedger(
                total=res_def.capacity, available=res_def.capacity
            )
            d_ledger = PhysicsDataNode(
                id=ledger_id,
                name=f"Ledger({res_def.name})",
                capacity=1,
                initial_tokens=1,
                initial_payload=initial_ledger,
            )
            physical_graph.nodes[ledger_id] = d_ledger

            # F_allocator
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
            physical_graph.nodes[allocator_id] = f_allocator

            # F_reclaimer
            f_reclaimer = PhysicsFuncNode(
                id=reclaimer_id,
                name=f"Reclaimer({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[reclaimer_id] = f_reclaimer

            # Wiring: Ledger <-> Allocator
            physical_graph.channels.append(
                Channel(ledger_id, "out", allocator_id, PortName.LEDGER_IN)
            )
            physical_graph.channels.append(
                Channel(allocator_id, PortName.LEDGER_OUT, ledger_id, "in")
            )

            # Wiring: Ledger <-> Reclaimer
            physical_graph.channels.append(
                Channel(ledger_id, "out", reclaimer_id, PortName.LEDGER_IN)
            )
            physical_graph.channels.append(
                Channel(reclaimer_id, PortName.LEDGER_OUT, ledger_id, "in")
            )

            # Request Buffer
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )
            physical_graph.nodes[d_req_buffer_id] = d_req_buffer

            # Buffer -> Allocator
            physical_graph.channels.append(
                Channel(d_req_buffer_id, "out", allocator_id, PortName.REQ)
            )
            # Recirculation: Allocator -> Buffer
            physical_graph.channels.append(
                Channel(allocator_id, PortName.REQ_OUT, d_req_buffer_id, "in")
            )

            # Release Buffer
            # Created here instead of implicitly later to ensure consistent ID
            rel_buffer_id = f"buffer.rel.{res_def.name}"
            d_rel_buffer = PhysicsDataNode(
                id=rel_buffer_id, name=f"RelBuffer({res_def.name})", capacity=1000
            )
            physical_graph.nodes[rel_buffer_id] = d_rel_buffer
            
            # Buffer -> Reclaimer
            physical_graph.channels.append(
                Channel(rel_buffer_id, "out", reclaimer_id, PortName.REL)
            )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            for res_name, amount in node_ir.constraints.items():
                broker_id = PhysicalIdGenerator.global_broker(res_name)
                req_buffer_id = f"buffer.req.{res_name}"

                # --- A. Request Chain ---
                # 1. D_const (Amount)
                d_amt_id = PhysicalIdGenerator.constant(node_ir.id, f"req_amt_{res_name}")
                d_amt = PhysicsDataNode(
                    id=d_amt_id,
                    name=f"Amt({res_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=amount,
                )
                physical_graph.nodes[d_amt_id] = d_amt

                # 2. F_probe (ConstProbe)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({res_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                physical_graph.nodes[f_probe_id] = f_probe

                # 3. F_req (Requestor)
                f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
                f_req = PhysicsFuncNode(
                    id=f_req_id,
                    name=f"Req({res_name})",
                    input_ports={"amount": PortDef("amount", PortRole.DATA)},
                    output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
                )
                physical_graph.nodes[f_req_id] = f_req

                # 4. Wiring: D_amt -> F_probe -> D_temp -> F_req -> D_req_buffer
                # We need intermediate data nodes because of Bipartite rule (F->D->F)
                
                # D_amt -> F_probe
                physical_graph.channels.append(
                    Channel(d_amt_id, "out", f_probe_id, "value")
                )

                # F_probe -> D_probed
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
                physical_graph.nodes[d_probed_id] = d_probed

                physical_graph.channels.append(
                    Channel(f_probe_id, "out", d_probed_id, "in")
                )
                
                # D_probed -> F_req
                physical_graph.channels.append(
                    Channel(d_probed_id, "out", f_req_id, "amount")
                )

                # F_req -> D_req_buffer (Global Buffer for the Broker)
                physical_graph.channels.append(
                    Channel(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")
                )

                # --- B. Grant Wiring ---
                # Broker (GNT) -> Bleacher (res_{name})
                # FILTER: Must match the Requestor's tag.
                # The Requestor sets tag = f_req.id (based on std implementation).
                # Wait, Requestor code: "tag=node.id". So tag is f_req_id.
                target_tag = f_req_id
                
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=broker_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )

                # --- C. Release Wiring ---
                # Stainer (res_{name}) -> Broker (REL)
                # We need a D_rel_buffer or connect directly to a D_rel?
                # The broker needs a REL input buffer.
                # Let's create a shared REL buffer for the broker too.
                rel_buffer_id = f"buffer.rel.{res_name}"
                if rel_buffer_id not in physical_graph.nodes:
                    d_rel_buffer = PhysicsDataNode(
                        id=rel_buffer_id, name=f"RelBuffer({res_name})", capacity=1000
                    )
                    physical_graph.nodes[rel_buffer_id] = d_rel_buffer
                    
                    # Buffer -> Broker
                    physical_graph.channels.append(
                        Channel(rel_buffer_id, "out", broker_id, PortName.REL)
                    )

                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )
~~~~~
~~~~~python.new
            for res_name, amount in node_ir.constraints.items():
                allocator_id = PhysicalIdGenerator.global_allocator(res_name)
                req_buffer_id = f"buffer.req.{res_name}"
                rel_buffer_id = f"buffer.rel.{res_name}"

                # --- A. Request Chain ---
                # 1. D_const (Amount)
                d_amt_id = PhysicalIdGenerator.constant(node_ir.id, f"req_amt_{res_name}")
                d_amt = PhysicsDataNode(
                    id=d_amt_id,
                    name=f"Amt({res_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=amount,
                )
                physical_graph.nodes[d_amt_id] = d_amt

                # 2. F_probe (ConstProbe)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({res_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                physical_graph.nodes[f_probe_id] = f_probe

                # 3. F_req (Requestor)
                f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
                f_req = PhysicsFuncNode(
                    id=f_req_id,
                    name=f"Req({res_name})",
                    input_ports={"amount": PortDef("amount", PortRole.DATA)},
                    output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
                )
                physical_graph.nodes[f_req_id] = f_req

                # 4. Wiring: D_amt -> F_probe -> D_temp -> F_req -> D_req_buffer
                # We need intermediate data nodes because of Bipartite rule (F->D->F)
                
                # D_amt -> F_probe
                physical_graph.channels.append(
                    Channel(d_amt_id, "out", f_probe_id, "value")
                )

                # F_probe -> D_probed
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
                physical_graph.nodes[d_probed_id] = d_probed

                physical_graph.channels.append(
                    Channel(f_probe_id, "out", d_probed_id, "in")
                )
                
                # D_probed -> F_req
                physical_graph.channels.append(
                    Channel(d_probed_id, "out", f_req_id, "amount")
                )

                # F_req -> D_req_buffer (Global Buffer for the Allocator)
                physical_graph.channels.append(
                    Channel(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")
                )

                # --- B. Grant Wiring ---
                # Allocator (GNT) -> Bleacher (res_{name})
                target_tag = f_req_id
                
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=allocator_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )

                # --- C. Release Wiring ---
                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )
~~~~~

#### Acts 5: 更新 Builder 测试

Builder 测试中关于 Broker 的断言需要更新。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
~~~~~
~~~~~python.old
    # 3. Assert Broker/Ledger creation
    # Used resource
    ledger_id = "canonical.resource.ledger.gpu"
    broker_id = "canonical.resource.broker.gpu"
    
    assert ledger_id in graph.nodes
    assert broker_id in graph.nodes
~~~~~
~~~~~python.new
    # 3. Assert Broker/Ledger creation
    # Used resource
    ledger_id = "canonical.resource.ledger.gpu"
    allocator_id = "canonical.resource.allocator.gpu"
    reclaimer_id = "canonical.resource.reclaimer.gpu"
    
    assert ledger_id in graph.nodes
    assert allocator_id in graph.nodes
    assert reclaimer_id in graph.nodes
~~~~~

#### Acts 6: 更新集成测试

更新 `func_map` 和断言逻辑。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_broker
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe
~~~~~
~~~~~python.new
# Import new ICs
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.probe.const import const_probe
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "broker" in node_id:
            func_map[node_id] = discrete_broker
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
~~~~~
~~~~~python.new
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "allocator" in node_id:
            func_map[node_id] = discrete_allocator
        elif "reclaimer" in node_id:
            func_map[node_id] = discrete_reclaimer
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    # Round 3: Broker fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    await reactor.step()
    await wait_idle()
    
    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
    
    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4: 
    # - The lucky Bleacher (who got GNT) fires.
    # - The Broker attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1). 
    #   Logic: 0 < 1. Reject & Recirculate.
    
    fired = await reactor.step()
    await wait_idle()
    
    # If Broker fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.
    
    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer
    
    # We loop until resource is released (Ledger becomes 1)
    max_steps = 20
    for _ in range(max_steps):
        await reactor.step()
        await wait_idle()
        
        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break
            
    assert ledger.available == 1
    
    # Now the second task can proceed.
    # Broker fires -> Grants -> Bleacher -> Worker -> Stainer
    for _ in range(10):
        if memory.get_count(req_buffer_id) == 0 and memory.get_count("buffer.rel.gpu") == 0:
             # If buffers are empty and tasks done, we are good.
             pass
        await reactor.step()
        await wait_idle()
~~~~~
~~~~~python.new
    # Round 3: Allocator fires.
    # It consumes Ledger + ONE request from Buffer.
    # Since capacity is 1, it Grants.
    await reactor.step()
    await wait_idle()
    
    # Ledger should now have 0 available
    ledger = memory.take(ledger_node_id).payload
    assert ledger.available == 0
    memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
    
    # Buffer should have 1 request remaining
    assert memory.get_count(req_buffer_id) == 1

    # Round 4: 
    # - The lucky Bleacher (who got GNT) fires.
    # - The Allocator attempts to fire again for the second request?
    #   Yes, it reads Ledger(0) and Request(1). 
    #   Logic: 0 < 1. Reject & Recirculate.
    
    fired = await reactor.step()
    await wait_idle()
    
    # If Allocator fired, it recirculated the request back to Buffer.
    # If Bleacher fired, it started the triad.
    
    # Let's run until one Task completes (Stainer fires)
    # This involves: Worker -> Stainer -> RelBuffer -> Reclaimer -> Ledger
    
    # We loop until resource is released (Ledger becomes 1)
    max_steps = 30
    for _ in range(max_steps):
        await reactor.step()
        await wait_idle()
        
        # Check if resource returned
        ledger = memory.take(ledger_node_id).payload
        memory.put(physical_graph.nodes[ledger_node_id], Token(payload=ledger))
        if ledger.available == 1:
            break
            
    assert ledger.available == 1
    
    # Now the second task can proceed.
    # Allocator fires -> Grants -> Bleacher -> Worker -> Stainer -> Reclaimer
    for _ in range(20):
        if memory.get_count(req_buffer_id) == 0 and memory.get_count("buffer.rel.gpu") == 0:
             # If buffers are empty and tasks done, we are good.
             pass
        await reactor.step()
        await wait_idle()
~~~~~

### 下一步建议
我们已经将 broker 拆分为 allocator 和 reclaimer。现在应该重新运行测试，确认死锁问题已解决。
