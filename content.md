好的，我们来实施“Probe 归位”这一重构任务。

你的分析完全正确。当前的 `cascade-compiler` 为了“优化”，直接将常量（Literal）作为带 `initial_payload` 的 `PhysicsDataNode` 连接到任务上，这严重违反了 **“物理层纯粹性优于编译时性能”** 的原则，并破坏了 **“探测器模型 (Probe Model)”** 的统一性。

我将生成一个计划，修改 `Builder` 的行为。对于所有常量输入，我们将严格遵循白皮书定义的物理定律，生成一个完整的 `D_const -> F_probe -> D_probed -> F_bleacher` 链条。这会消除编译器中的一个“特殊情况”处理逻辑，使物理图的生成更加统一和可预测，并将优化的责任正确地推迟到 JIT 阶段。

## [WIP] refactor: 为常量输入实现标准的探测器模型

### 用户需求
修改 `Builder`，对于常量输入，不再直接生成带 Payload 的 `D_const` 数据节点，而是生成 `F_probe` (指向 `const_probe` 实现) + `D_val` 的标准物理结构，以符合架构白皮书的“探测器模型”。

### 评论
这是对 `cascade-compiler` 的一次至关重要的架构对齐。通过消除对常量的特殊处理，我们强制所有输入（无论是来自上游任务还是字面量）都遵循统一的物理路径。这不仅极大地简化了编译器的逻辑，还使得物理图成为逻辑图的全息投影，为未来的 JIT 优化（如常量折叠）和全链路可观测性奠定了坚实的基础。

### 目标
1.  定位 `cascade-compiler/src/cascade/compiler/backend/builder.py` 中处理字面量输入的逻辑块。
2.  移除创建带 `initial_payload` 的 `PhysicsDataNode` 并直接连接到 `Bleacher` 的过早优化代码。
3.  替换为创建 `D_const -> F_probe -> D_probed` 物理链条的标准逻辑。
4.  将这个链条的末端（`D_probed`）正确连接到目标任务的 `Bleacher` 节点上。

### 基本原理
根据 **Cascade 3.0 架构白皮书**，所有参数都应被视为“动态采样动作”。当前的实现破坏了这一点，它让编译器扮演了 JIT 的角色，提前进行了“常量折叠”。

本次重构将恢复物理层的纯粹性。新的拓扑结构将是：
1.  `D_const`: 一个持有字面量值的、带 `initial_payload` 的 `PhysicsDataNode`。
2.  `F_probe`: 一个 `PhysicsFuncNode`，它接收 `D_const` 的令牌，执行 `const_probe` 逻辑（本质上是一个身份函数），然后输出结果。
3.  `D_probed`: 一个标准的中间 `PhysicsDataNode`，用于接收 `F_probe` 的结果，并遵守二分图规则。
4.  `F_bleacher`: `D_probed` 的输出最终连接到目标任务的 `Bleacher` 节点，完成输入。

这个看似“冗余”的结构是正确的，因为它在物理层保留了完整的逻辑语义，将优化的权力完全交给了运行时。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/probe-model #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 Builder 以实现探测器模型

我们将修改 `builder.py`，将处理常量输入的逻辑替换为创建和连接探测器节点的标准流程。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # Case B: Literal Value (Constant)
                else:
                    # Create a dedicated DataNode for this constant
                    const_node_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                    const_node = PhysicsDataNode(
                        id=const_node_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
                    wire.add_node(const_node)

                    # Wire Const -> Bleacher
                    wire.connect(
                        const_node_id, "out", target_subgraph.bleacher.id, arg_name
                    )
~~~~~
~~~~~python.new
                # Case B: Literal Value (Constant) - Use Probe Model
                else:
                    # 1. D_const (DataNode holding the literal value)
                    d_const_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                    d_const = PhysicsDataNode(
                        id=d_const_id,
                        name=f"Const({arg_name})",
                        capacity=1,
                        initial_tokens=1,
                        initial_payload=source_ref,
                    )
                    wire.add_node(d_const)

                    # 2. F_probe (The probe node for constants)
                    f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, arg_name)
                    f_probe = PhysicsFuncNode(
                        id=f_probe_id,
                        name=f"Probe({arg_name})",
                        input_ports={"value": PortDef("value", PortRole.DATA)},
                        output_ports={"out": PortDef("out", PortRole.DATA)},
                    )
                    wire.add_node(f_probe)

                    # 3. D_probed (Intermediate data node to connect to Bleacher)
                    d_probed_id = f"{f_probe_id}.out"
                    d_probed = PhysicsDataNode(
                        id=d_probed_id, name=f"Probed({arg_name})"
                    )
                    wire.add_node(d_probed)

                    # 4. Wiring
                    # D_const -> F_probe
                    wire.connect(d_const_id, "out", f_probe_id, "value")
                    # F_probe -> D_probed
                    wire.connect(f_probe_id, "out", d_probed_id, "in")
                    # D_probed -> Target Bleacher
                    wire.connect(
                        d_probed_id, "out", target_subgraph.bleacher.id, arg_name
                    )
~~~~~

### 下一步建议
我们已经完成了“Probe 归位”的重构。根据 `识别出的过早优化和架构违规.md` 中定义的计划，下一步是解决“隐式启动”问题。

我建议我们立即开始实施**“Pulse 引入”**：在图中引入一个全局的 `Pulse` 信号流，并修改编译器，使其能够识别所有源探测器（Source Probes）并自动将它们连接到这个全局启动脉冲上。这将为系统提供一个清晰、统一的“控制平面”，彻底解决僵尸节点问题。如果你同意，我将生成相应的计划。
