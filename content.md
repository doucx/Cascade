Plan 1:
1. 读取相关文件内容。
2. 根据路线图生成修复的 `patch_file` 指令。
3. 提交修改。

先读取文件。简要回答
我们将执行修复物理布线策略的路线图。首先，我们将修改 Expander 以确保 Launcher 始终具有 Pulse 端口，然后我们将更新 PulseExpansionPolicy 以更智能地检测“源节点”，即使它们具有静态输入或资源注入。

## [WIP] fix(compiler): standardize pulse port and refine source detection logic

### 用户需求
修复编译器中的一个缺陷：当任务具有静态参数或资源注入（通过 `Inject`）但没有上游任务依赖时，编译器未能正确识别其为“源节点”（需要 Pulse 触发），或者因为 Expander 未创建 Pulse 端口导致 Wiring 阶段失败。

### 评论
这是一个关键的修复，对于支持依赖注入（DI）和参数化任务至关重要。目前的逻辑假设“任何输入都意味着有上游依赖”，这在引入 DI 和常量输入后不再成立。通过解耦“物理端口存在性”与“触发逻辑”，架构将变得更加健壮。

### 目标
1.  修改 `Expander`，使 `LauncherNode` 总是包含 `__pulse__` 端口，无论是否有其他输入。
2.  修改 `PulseExpansionPolicy`，使其能够区分“上游节点引用”和“静态/注入输入”，从而正确地为孤立的参数化任务创建 Pulse 源。

### 基本原理
1.  **物理层 (Expander)**: 物理节点应具备接收所有可能信号的能力。端口的存在不应取决于当前的连接逻辑，而应由 Spec 定义。未连接的端口在 Reactor 中是无害的。
2.  **逻辑层 (Policy)**: 只有当一个节点确实依赖于另一个节点的**执行结果**（显式依赖、数据流、条件）时，它才不需要自举脉冲。静态参数和资源注入是在节点启动前准备好的，不构成执行流的阻塞依赖。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/executor #scope/core #ai/instruct #task/domain/compiler #task/object/wiring-policy #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 读取相关文件
首先，我们需要读取 `Expander` 和 `PulseExpansionPolicy` 的源代码，以确定修改的精确上下文。

~~~~~act
read_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~

~~~~~act
read_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~

#### Acts 2: 实施修复 - Expander
现在我们将修改 `Expander`，使其总是添加 `__pulse__` 端口。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # 2.6 Pulse (if pure source)
        if not launcher_inputs:
            pulse_name = LauncherSpec.pulse.name
            launcher_inputs[pulse_name] = PortDef(pulse_name, PortRole.SIGNAL)

        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
~~~~~
~~~~~python.new
        # 2.6 Pulse (Always Available)
        # We always expose the pulse port. If this is an intermediate node, this port
        # might remain unwired. The Reactor will decide which ports to wait for based
        # on actual connections.
        pulse_name = LauncherSpec.pulse.name
        if pulse_name not in launcher_inputs:
            launcher_inputs[pulse_name] = PortDef(pulse_name, PortRole.SIGNAL)

        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]
~~~~~

#### Acts 3: 实施修复 - PulseExpansionPolicy
接下来，我们更新 `PulseExpansionPolicy` 的判定逻辑，使其不再因为存在静态输入或约束而拒绝创建 Pulse 源。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~
~~~~~python.old
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # A true source has no inputs, dependencies, conditions, or constraints.
        is_true_source = (
            not node_ir.inputs
            and not node_ir.dependencies
            and not node_ir.condition
            and not node_ir.constraints
        )

        if is_true_source:
            d_pulse_id = PhysicalIdGenerator.pulse_source(
                node_ir.current_node_instance_hash
            )
            d_pulse = PhysicsDataNode(
                id=d_pulse_id,
                name=f"Pulse({node_ir.current_node_instance_hash})",
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            subgraph.nodes[d_pulse.id] = d_pulse
            subgraph.controls["pulse_source"] = d_pulse
~~~~~
~~~~~python.new
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # Determine if the node needs a self-bootstrapping pulse.
        # It needs a pulse if it has NO upstream execution dependencies.

        # 1. Check Explicit Sequence Dependencies (.after())
        has_dependencies = len(node_ir.dependencies) > 0

        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        for value in node_ir.inputs.values():
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break

        # 3. Check Condition (.run_if())
        has_condition = node_ir.condition is not None

        # Decision: If there are no upstream triggers, we must provide a pulse.
        # Note: Static inputs (constants) and Resource Constraints do not count as
        # execution dependencies; they are pre-requisites but not triggers.
        needs_pulse = not (has_dependencies or has_data_dependency or has_condition)

        if needs_pulse:
            d_pulse_id = PhysicalIdGenerator.pulse_source(
                node_ir.current_node_instance_hash
            )
            d_pulse = PhysicsDataNode(
                id=d_pulse_id,
                name=f"Pulse({node_ir.current_node_instance_hash})",
                capacity=1,
                initial_tokens=1,
            )
            ctx.wire.add_node(d_pulse)
            subgraph.nodes[d_pulse.id] = d_pulse
            subgraph.controls["pulse_source"] = d_pulse
~~~~~

### 下一步建议
我们已经完成了编译器核心逻辑的修复。建议进行全面的集成测试，特别是针对 `Inject` 功能和带有参数的根任务，以验证修复的有效性。由于无法直接运行测试，建议将这些更改提交到代码库。
