简要回答：
好的，我将执行 **Phase 2: Compiler Backend Optimization**。这将涉及修改编译器策略，使其停止生成已废弃的 `F_probe` 节点，转而建立直接的 `D_const -> F_target` 连接。

## [WIP] refactor: 实施 Phase 2 - 编译器后端移除 Probe 依赖

### 用户需求
根据路线图 Phase 2：
1.  重构 `ParameterWiringPolicy`，移除 `F_probe` 生成逻辑，改为 `D_const` 直连 `Bleacher`。
2.  (隐式需求) 重构 `DiscreteResourcePrism`，同样移除 `F_probe` 生成逻辑，改为 `D_const` 直连 `F_req` (Resource Requestor)，以确保资源子系统也符合新架构。

### 评论
这是为了配合 Phase 1 中 Probe 组件的物理移除。如果不进行此步骤，编译器生成的物理图将包含无法执行的幻影节点 (`F_probe`)。
此次修改简化了物理图结构，减少了节点数量（每个常量减少 2 个节点：F_probe 和 D_probed），提高了图的紧凑性，同时完全符合二分图规则。

### 目标
确保编译器生成的物理图不再包含任何 `F_probe` 节点，且数据流（常量注入）依然正确。

### 基本原理
*   **物理层无数据公理**: 物理层不需要“采样”常量，常量在物理图中表现为预置了 Token 的 DataNode。
*   **二分图规则**: DataNode (`D_const`) 可以直接连接到 FuncNode (`Bleacher` 或 `F_req`)，中间不需要额外的 FuncNode (`F_probe`) 做中转。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #concept/physics #scope/core #ai/instruct
#task/domain/vm #task/object/compiler-backend #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 修改 ParameterWiringPolicy

修改参数连线策略，去除 Case B 中的 `F_probe` 和 `D_probed`，实现 `D_const` -> `Bleacher` 的直接连接。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
~~~~~
~~~~~python.old
            # Case B: Literal Value (Constant) - Use Probe Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(
                    node_ir.current_node_instance_hash, input_key
                )
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. F_probe (The probe node for constants)
                f_probe_id = PhysicalIdGenerator.probe_const(
                    node_ir.current_node_instance_hash, input_key
                )
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({port_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                ctx.wire.add_node(f_probe)

                # 3. D_probed (Intermediate data node to connect to Bleacher)
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name=f"Probed({port_name})")
                ctx.wire.add_node(d_probed)

                # 4. Wiring
                # D_const -> F_probe
                ctx.wire.connect(d_const_id, "out", f_probe_id, "value")
                # F_probe -> D_probed
                ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")
                # D_probed -> Target Bleacher
                ctx.wire.connect(d_probed_id, "out", subgraph.bleacher.id, port_name)
~~~~~
~~~~~python.new
            # Case B: Literal Value (Constant) - Direct Materialization Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(
                    node_ir.current_node_instance_hash, input_key
                )
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. Wiring: D_const -> Bleacher
                # Note: This is a direct D -> F connection, which is valid in Bipartite graphs.
                # The Strategy layer will be responsible for materializing the literal value
                # into a Ref during the loading phase.
                ctx.wire.connect(d_const_id, "out", subgraph.bleacher.id, port_name)
~~~~~

#### Acts 2: 修改 DiscreteResourcePrism

同样地，修改离散资源棱镜中的请求连线逻辑，去除 `F_probe`，实现 `D_amt` -> `F_req` 的直接连接。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/prisms/discrete.py
~~~~~
~~~~~python.old
        # 2. F_probe (ConstProbe)
        f_probe_id = PhysicalIdGenerator.probe_const(
            node_ir.current_node_instance_hash, res_name
        )
        f_probe = PhysicsFuncNode(
            id=f_probe_id,
            name=f"Probe({res_name})",
            input_ports={"value": PortDef("value", PortRole.DATA)},
            output_ports={"out": PortDef("out", PortRole.DATA)},
        )
        ctx.wire.add_node(f_probe)

        # 3. F_req (Requestor)
        f_req_id = PhysicalIdGenerator.requestor(
            node_ir.current_node_instance_hash, res_name
        )
        f_req = PhysicsFuncNode(
            id=f_req_id,
            name=f"Req({res_name})",
            input_ports={"amount": PortDef("amount", PortRole.DATA)},
            output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
        )
        ctx.wire.add_node(f_req)

        # 4. Wiring
        # D_amt -> F_probe
        ctx.wire.connect(d_amt_id, "out", f_probe_id, "value")

        # F_probe -> D_probed
        d_probed_id = f"{f_probe_id}.out"
        d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
        ctx.wire.add_node(d_probed)

        ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")

        # D_probed -> F_req
        ctx.wire.connect(d_probed_id, "out", f_req_id, "amount")
~~~~~
~~~~~python.new
        # 2. F_req (Requestor)
        f_req_id = PhysicalIdGenerator.requestor(
            node_ir.current_node_instance_hash, res_name
        )
        f_req = PhysicsFuncNode(
            id=f_req_id,
            name=f"Req({res_name})",
            input_ports={"amount": PortDef("amount", PortRole.DATA)},
            output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
        )
        ctx.wire.add_node(f_req)

        # 3. Wiring
        # D_amt -> F_req (Direct connection)
        ctx.wire.connect(d_amt_id, "out", f_req_id, "amount")
~~~~~

### 下一步建议

我们已经完成了编译器的改造。现在的物理图是“纯净”的，不再依赖任何 Probe 组件。
接下来是 **Phase 3: 策略层重构**，这是本次迁移的核心。我们需要实现全新的 `CascadeVMStrategy`，它将负责环境初始化、图编译、常量物质化（Materialization）、物理图外科手术（Egress 注入）以及最终的执行驱动。

我建议按照 Phase 3 的子阶段顺序，从 **创建 `CascadeVMStrategy` 并实现 `_materialize_constants`** 开始。
