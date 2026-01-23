我明白了，上一次的重构没有覆盖到编译器的 `expander.py` 部分。它仍然在尝试访问已被移除的 `NodeIR.inputs` 属性。

这是一个预料之中的连锁反应，因为我们正在进行架构级的重构。我将立即修复它。

## [WIP] fix(compiler): 更新 expander 以适应新的 NodeIR 规约

### 错误分析

**错误现象**:
`AttributeError: 'NodeIR' object has no attribute 'inputs'`。

**根本原因**:
在之前的计划中，我们用 `args` 和 `kwargs` 字段替换了 `NodeIR` 的 `inputs` 字段。但是，位于 `packages/cascade-compiler/src/cascade/compiler/backend/expander.py` 的 `Expander` 类在构建 `LauncherNode` 的端口时，仍然在引用旧的 `inputs` 属性来确定需要创建哪些动态输入端口。

### 用户需求

确保编译器的所有部分都与新的 `NodeIR` 规约兼容。

### 评论

这是一个简单的修复，属于我们正在进行的 IR 重构任务的一部分。它强调了在进行此类核心数据结构更改时，进行全代码库影响分析的重要性。

### 目标

修改 `expander.py` 中的 `expand_node` 方法，使其从 `node_ir.args` 和 `node_ir.kwargs` 中收集信息，而不是从 `node_ir.inputs`。

### 基本原理

我们将修改 `Expander` 中的循环，使其迭代 `node_ir.kwargs` 的键，并根据 `node_ir.args` 的长度来确定位置参数的数量，从而正确地为 `LauncherNode` 创建所有必要的输入端口定义。

### 标签

#intent/fix #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `expander.py` 以使用 `args` 和 `kwargs`

我们将修复 `Expander` 对 `NodeIR` 的使用。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # 2.2 Dynamic Args from Inputs
        for input_key in node_ir.inputs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")
~~~~~
~~~~~python.new
        # 2.2 Dynamic Args from Inputs
        # Positional args are represented by their index as a string
        for i in range(len(node_ir.args)):
            input_key = str(i)
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # Keyword args
        for input_key in node_ir.kwargs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")
~~~~~

#### Acts 2: 更新 `ParameterExpansionPolicy`

`ParameterExpansionPolicy` 同样也引用了 `inputs`，需要一并修复。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/parameter.py
~~~~~
~~~~~python.old
class ParameterExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        for input_key, source_ref in node_ir.inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                d_dep_id = f"dep.{source_ref}.to.{node_ir.current_node_instance_hash}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")

                # Register the new node
                ctx.wire.add_node(d_dep)
                subgraph.nodes[d_dep.id] = d_dep
                subgraph.controls[f"dep_for_{input_key}"] = d_dep

            # Case B: Literal Value - Create D_const node
            else:
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

                # Register the new node
                ctx.wire.add_node(d_const)
                subgraph.nodes[d_const.id] = d_const
                subgraph.constants[input_key] = d_const
~~~~~
~~~~~python.new
class ParameterExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # Combine args and kwargs for unified processing
        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                d_dep_id = f"dep.{source_ref}.to.{node_ir.current_node_instance_hash}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")

                # Register the new node
                ctx.wire.add_node(d_dep)
                subgraph.nodes[d_dep.id] = d_dep
                subgraph.controls[f"dep_for_{input_key}"] = d_dep

            # Case B: Literal Value - Create D_const node
            else:
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

                # Register the new node
                ctx.wire.add_node(d_const)
                subgraph.nodes[d_const.id] = d_const
                subgraph.constants[input_key] = d_const
~~~~~

#### Acts 3: 更新 `PulseExpansionPolicy`

`PulseExpansionPolicy` 也需要更新。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/pulse.py
~~~~~
~~~~~python.old
        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        for value in node_ir.inputs.values():
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break
~~~~~
~~~~~python.new
        # 2. Check Data Dependencies (inputs referencing other nodes)
        has_data_dependency = False
        all_input_values = list(node_ir.args) + list(node_ir.kwargs.values())
        for value in all_input_values:
            # IRGenerator stores upstream references as strings (Logical UUIDs).
            # We check if this string corresponds to a known SubGraph ID in the current graph.
            if isinstance(value, str) and value in ctx.subgraphs:
                has_data_dependency = True
                break
~~~~~

#### Acts 4: 更新 `ParameterWiringPolicy`

最后，`ParameterWiringPolicy` 也需要更新。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
~~~~~
~~~~~python.old
class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.lander is not None

                # Retrieve the intermediate node created during expansion
                d_dep = subgraph.controls[f"dep_for_{input_key}"]

                # Connect: Source Lander -> D_dep
                # Note: LanderSpec uses 'output_default' just like StainerSpec did
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_dep.id,
                    "in",
                )

                # Connect: D_dep -> Target Launcher
                ctx.wire.connect(d_dep.id, "out", subgraph.launcher.id, port_name)

            # Case B: Literal Value (Constant)
            else:
                # Retrieve the constant node created during expansion
                d_const = subgraph.constants[input_key]

                # Connect: D_const -> Launcher
                ctx.wire.connect(d_const.id, "out", subgraph.launcher.id, port_name)
~~~~~
~~~~~python.new
class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.launcher is not None

        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # Resolve the actual port name on the Launcher.
            if input_key.isdigit():
                idx = int(input_key)
                arg_def = (
                    node_ir.task.args[idx] if idx < len(node_ir.task.args) else None
                )

                # For *args, the port name is the index itself, not the arg name (e.g. 'args')
                if arg_def and arg_def.kind != ArgumentKind.VAR_POSITIONAL:
                    port_name = arg_def.name
                else:
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.lander is not None

                # Retrieve the intermediate node created during expansion
                d_dep = subgraph.controls[f"dep_for_{input_key}"]

                # Connect: Source Lander -> D_dep
                # Note: LanderSpec uses 'output_default' just like StainerSpec did
                ctx.wire.connect(
                    source_subgraph.lander.id,
                    LanderSpec.output_default.name,
                    d_dep.id,
                    "in",
                )

                # Connect: D_dep -> Target Launcher
                ctx.wire.connect(d_dep.id, "out", subgraph.launcher.id, port_name)

            # Case B: Literal Value (Constant)
            else:
                # Retrieve the constant node created during expansion
                d_const = subgraph.constants[input_key]

                # Connect: D_const -> Launcher
                ctx.wire.connect(d_const.id, "out", subgraph.launcher.id, port_name)
~~~~~

### 下一步建议

我们已经修复了编译流程中所有对旧 `NodeIR.inputs` 属性的引用。现在，我们应该再次运行完整的测试套件。如果所有测试都通过，就证明这次架构重构已经成功，我们可以准备提交这些变更了。
