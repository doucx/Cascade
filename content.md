好的，我来分析并修复这个 `AssertionError`。

这是一个非常深刻的 Bug，它暴露了我们对物理模型理解的一个盲点。测试失败是正确的，它捕获了一个由编译器引入的、物理上不可能实现的死锁。

**错误分析**:
1.  **根本原因**: 在 `Builder` 中，我们将 `F_broker` 节点定义为一个需要**三个**输入端口都必须有 Token 才能激发的“三输入与门”：`ledger_in`, `req_in`, 和 `rel_in`。
2.  **物理矛盾**: 在测试开始时，`D_ledger` 和 `D_req_buffer` 中有 Token，但 `D_rel_buffer` 是空的（因为没有任何任务完成并释放资源）。
3.  **正确行为**: `Reactor` 引擎正确地遵循了物理定律：由于 `rel_in` 端口的上游 `D_rel_buffer` 是空的，`F_broker` 的“全准入激发”条件永远无法满足，因此它**永远不会被激发**。
4.  **测试失败**: Broker 从未运行，因此 `D_ledger` 中的资源从未被消耗。当测试代码检查 `ledger.available` 时，它仍然是初始值 `1`，而我们错误地期望它变成 `0`。

**解决方案**:
我们必须将 Broker 的“请求处理”和“释放处理”在物理拓扑上解耦。它们是两个独立的物理事件，不能被强制合并到一个原子操作中。

我们将把一个逻辑上的 Broker 拆分为两个物理上的函数节点：
*   `F_broker_req`: 只有两个输入 (`ledger_in`, `req_in`)。
*   `F_broker_rel`: 只有两个输入 (`ledger_in`, `rel_in`)。

这两个物理节点将使用**完全相同**的 `discrete_broker` Python 函数作为其逻辑，但它们在图中有不同的“引脚”定义。它们会竞争同一个 `D_ledger` 状态节点，这正确地模拟了对共享资源的互斥访问。

---

## [WIP] fix(compiler): 将 Broker 拆分为 Req/Rel 物理节点以解决死锁

### 用户需求
修复 `test_resource_backpressure.py` 中的 `AssertionError`。

### 错误分析
当前 `Builder` 生成的 `F_broker` 节点错误地要求 `req_in` 和 `rel_in` 端口同时满足，导致在只有请求而没有释放的初始状态下，Broker 无法被 Reactor 激发，造成死锁。

### 评论
这是一个关键的架构修正。它强制我们将逻辑功能（Broker）映射到正确的物理拓扑上，确保了系统的行为符合“全准入激发”的物理定律，根除了由编译器设计引入的死锁。

### 目标
1.  更新 `PhysicalIdGenerator` 以支持 `broker_req` 和 `broker_rel` 节点。
2.  重构 `Builder`，为每种资源创建两个 Broker 物理节点，并将请求和释放流分别连接到它们。
3.  更新 `test_resource_backpressure.py` 的 `function_map`，将两个新的节点 ID 都映射到 `discrete_broker` 函数。

### 基本原理
通过将单一的、多输入 Broker 节点拆分为两个职责更单一的节点，我们解决了物理层“或”逻辑缺失的问题。现在，请求处理和释放处理可以独立地被激发，它们通过对共享 `D_ledger` 节点的竞争来实现正确的互斥。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #concept/resource #scope/core #ai/instruct #task/domain/compiler #task/object/builder #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 更新命名生成器

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
    def global_broker_req(resource_name: str) -> str:
        return f"canonical.resource.broker.req.{resource_name}"

    @staticmethod
    def global_broker_rel(resource_name: str) -> str:
        return f"canonical.resource.broker.rel.{resource_name}"
~~~~~

#### Acts 2: 重构 Builder 的 Broker 创建逻辑

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
~~~~~
~~~~~python.new
        # 1. Create Resource Brokers (F_broker + internal Ledger loop)
        for res_def in environment.resources:
            req_broker_id = PhysicalIdGenerator.global_broker_req(res_def.name)
            rel_broker_id = PhysicalIdGenerator.global_broker_rel(res_def.name)
            ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

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

            # F_broker_req: Handles requests
            f_broker_req = PhysicsFuncNode(
                id=req_broker_id,
                name=f"Broker.Req({res_def.name})",
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
            physical_graph.nodes[req_broker_id] = f_broker_req

            # F_broker_rel: Handles releases
            f_broker_rel = PhysicsFuncNode(
                id=rel_broker_id,
                name=f"Broker.Rel({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                },
            )
            physical_graph.nodes[rel_broker_id] = f_broker_rel

            # Wire the Ledger Loop for BOTH brokers
            for broker_id in [req_broker_id, rel_broker_id]:
                # D_ledger -> F_broker
                physical_graph.channels.append(
                    Channel(ledger_id, "out", broker_id, PortName.LEDGER_IN)
                )
                # F_broker -> D_ledger
                physical_graph.channels.append(
                    Channel(broker_id, PortName.LEDGER_OUT, ledger_id, "in")
                )
~~~~~

#### Acts 3: 重构 Builder 的 Broker 连接逻辑

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            for res_name, amount in node_ir.constraints.items():
                broker_id = PhysicalIdGenerator.global_broker(res_name)
                req_buffer_id = f"buffer.req.{res_name}"
~~~~~
~~~~~python.new
            for res_name, amount in node_ir.constraints.items():
                req_broker_id = PhysicalIdGenerator.global_broker_req(res_name)
                rel_broker_id = PhysicalIdGenerator.global_broker_rel(res_name)
                req_buffer_id = f"buffer.req.{res_name}"
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
            # Connect Buffer -> Broker
            physical_graph.channels.append(
                Channel(
                    source_node_id=req_buffer_id,
                    source_port="out",
                    target_node_id=req_broker_id,
                    target_port=PortName.REQ,
                )
            )

            # Connect Recirculation: Broker -> Buffer
            physical_graph.channels.append(
                Channel(
                    source_node_id=req_broker_id,
                    source_port=PortName.REQ_OUT,
                    target_node_id=req_buffer_id,
                    target_port="in",
                )
            )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
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
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=req_broker_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )

                # --- C. Release Wiring ---
                rel_buffer_id = f"buffer.rel.{res_name}"
                if rel_buffer_id not in physical_graph.nodes:
                    d_rel_buffer = PhysicsDataNode(
                        id=rel_buffer_id, name=f"RelBuffer({res_name})", capacity=1000
                    )
                    physical_graph.nodes[rel_buffer_id] = d_rel_buffer
                    
                    # Buffer -> RelBroker
                    physical_graph.channels.append(
                        Channel(rel_buffer_id, "out", rel_broker_id, PortName.REL)
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

#### Acts 4: 修复集成测试 `function_map`

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "broker" in node_id:
            func_map[node_id] = discrete_broker
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
~~~~~
~~~~~python.new
    for node_id in physical_graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif node_id.startswith("canonical.resource.broker."):
            func_map[node_id] = discrete_broker
        elif node_id.startswith("req."):
            func_map[node_id] = resource_requestor
~~~~~

### 下一步建议
我们已经修复了编译器的核心物理模型。现在，让我们重新运行完整的测试套件，以确保这一重大重构没有引入意料之外的回归。如果所有测试通过，我们将完成“Broker 归位”战略，并可以自信地继续执行“Probe 归位”战略。
