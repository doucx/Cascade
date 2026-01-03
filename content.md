简要回答

好的，我将生成一个计划来完善 Compiler Frontend，使其支持 `run_if` 和 `_dependencies` 的逻辑映射。

## [WIP] feat(compiler): 实现 Frontend 对 run_if 和 dependencies 的支持

### 用户需求
在 `cascade-compiler` 中实现对 `LazyResult` 的 `run_if` (条件执行) 和 `_dependencies` (显式序列依赖) 属性的支持。这意味着 Compiler Frontend 需要解析这些关系，生成包含相应字段的 `NodeIR`，并且 Compiler Backend 需要将这些逻辑关系展开为物理图中的连接。

### 评论
这是 Phase 2 (Compiler Intelligence) 的关键一步。目前编译器只能处理数据依赖 (Data Dependency)，无法处理控制流 (Control Flow) 和纯时序依赖 (Sequence Dependency)。完成此任务后，Cascade 将具备表达复杂 DAG 的能力。

### 目标
1.  **Spec**: 更新 `NodeIR` 模型，增加 `condition` 和 `dependencies` 字段。
2.  **Hashing**: 更新 `HashingService`，将条件和依赖的具体的 Node ID 纳入哈希计算（而不仅仅是检查存在性），确保哈希的唯一性和确定性。
3.  **Frontend**: 更新 `IRGenerator`，使其在遍历 `LazyResult` 时递归解析 `_condition` 和 `_dependencies`。
4.  **Backend**: 更新 `Expander`，将逻辑上的条件和依赖映射为物理层 `Bleacher` 的 `SIGNAL` 输入端口。

### 基本原理
*   **Hashlife 对齐**: 节点的身份 (`Instance Hash`) 必须由其所有输入决定，包括隐式的控制流输入。因此 `HashingService` 必须包含这些信息。
*   **物理映射**: 在物理层，所有的依赖（无论是数据的还是控制的）最终都表现为“通道连接”。
    *   `_dependencies` 映射为从上游 `Stainer` 到下游 `Bleacher` 的 `SIGNAL` 通道（下游只关心“收到Token”，不关心内容）。
    *   `run_if` 映射为从条件节点到 `Bleacher` 的特定端口连接。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/frontend #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 Spec 中的 NodeIR 定义

我们需要在 `NodeIR` 中增加字段来存储控制流信息。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class NodeIR:
    id: str

    name: str

    task: TaskDef

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class NodeIR:
    id: str

    name: str

    task: TaskDef

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)

    # The ID of the node that determines if this node should run
    condition: Optional[str] = None

    # IDs of nodes that must complete before this node starts (Sequence dependency)
    dependencies: List[str] = field(default_factory=list)
~~~~~

#### Acts 2: 更新 HashingService 以包含控制流信息

更新哈希计算逻辑，确保 `_condition` 和 `_dependencies` 参与哈希计算。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
~~~~~
~~~~~python.old
        # 5. Metadata
        if getattr(result, "_condition", None):
            components.append("Condition:PRESENT")

        # 6. Constraints
~~~~~
~~~~~python.new
        # 5. Metadata
        if getattr(result, "_condition", None):
            # We need the ID of the condition node
            cond = result._condition
            # Handle potential MappedLazyResult or other types in condition if necessary
            # For now assuming LazyResult or similar which is in dep_nodes
            if hasattr(cond, "_uuid") and cond._uuid in dep_nodes:
                node = dep_nodes[cond._uuid]
                node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
                components.append(f"ConditionID:{node_id}")
            else:
                components.append("Condition:UNKNOWN")

        if getattr(result, "_dependencies", None):
            deps = result._dependencies
            if deps:
                components.append("Dependencies:[")
                # Sort by UUID to ensure stable hash
                sorted_deps = sorted(deps, key=lambda x: x._uuid)
                for dep in sorted_deps:
                    if dep._uuid in dep_nodes:
                        node = dep_nodes[dep._uuid]
                        node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
                        components.append(f"DepID:{node_id}")
                    else:
                        components.append("DepID:UNKNOWN")
                components.append("]")

        # 6. Constraints
~~~~~

#### Acts 3: 更新 IRGenerator 递归解析逻辑

更新 `IRGenerator` 以处理 `_condition` 和 `_dependencies` 的递归访问，并填充 `NodeIR`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        # 1. Resolve Dependencies (Post-order)
        # We visit args and kwargs first to ensure dependencies are registered.
        # This gives us the "transformed" inputs where LazyResults are replaced by Node IDs.
        transformed_args = [self._visit(arg) for arg in lr.args]
        transformed_kwargs = {k: self._visit(v) for k, v in lr.kwargs.items()}

        # Note: We currently don't handle _dependencies (implicit sequence) or _condition
        # in the NodeIR inputs structure explicitly yet.
        # TODO: Add support for sequence dependencies and run_if conditions.

        # 2. Analyze Task Definition
        task_def = self.analyzer.analyze(lr.task)

        # 3. Compute Instance Hash (Node ID)
~~~~~
~~~~~python.new
        # 1. Resolve Dependencies (Post-order)
        # We visit args and kwargs first to ensure dependencies are registered.
        transformed_args = [self._visit(arg) for arg in lr.args]
        transformed_kwargs = {k: self._visit(v) for k, v in lr.kwargs.items()}

        # Handle Condition (visit it so it's registered)
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        # Handle Explicit Dependencies (visit them)
        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        # 2. Analyze Task Definition
        task_def = self.analyzer.analyze(lr.task)

        # 3. Compute Instance Hash (Node ID)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        def collect_deps(raw_obj):
            if isinstance(raw_obj, LazyResult):
                if raw_obj._uuid in self._visited:
                    node_id = self._visited[raw_obj._uuid]
                    dep_map[raw_obj._uuid] = self.nodes[node_id]
            elif isinstance(raw_obj, (list, tuple)):
                for x in raw_obj:
                    collect_deps(x)
            elif isinstance(raw_obj, dict):
                for x in raw_obj.values():
                    collect_deps(x)

        for arg in lr.args:
            collect_deps(arg)
        for val in lr.kwargs.values():
            collect_deps(val)

        node_id = self.hashing_service.compute_node_instance_hash(task_def, lr, dep_map)

        # 4. Construct NodeIR
        # Flatten args and kwargs into a single 'inputs' dictionary
        inputs = {}
        for i, val in enumerate(transformed_args):
            inputs[str(i)] = val
        for k, val in transformed_kwargs.items():
            inputs[k] = val

        # Handle Constraints
        constraints = {}
        if lr._constraints:
            # We currently assume constraint values are literals.
            # TODO: Handle dynamic constraints (LazyResult in constraints)
            constraints = lr._constraints.requirements.copy()

        node_ir = NodeIR(
            id=node_id,
            name=task_def.name,
            task=task_def,
            inputs=inputs,
            constraints=constraints,
        )
~~~~~
~~~~~python.new
        def collect_deps(raw_obj):
            if isinstance(raw_obj, LazyResult):
                if raw_obj._uuid in self._visited:
                    node_id = self._visited[raw_obj._uuid]
                    dep_map[raw_obj._uuid] = self.nodes[node_id]
            elif isinstance(raw_obj, (list, tuple)):
                for x in raw_obj:
                    collect_deps(x)
            elif isinstance(raw_obj, dict):
                for x in raw_obj.values():
                    collect_deps(x)

        for arg in lr.args:
            collect_deps(arg)
        for val in lr.kwargs.values():
            collect_deps(val)
        
        # Also collect deps for condition and dependencies for hashing
        if lr._condition:
            collect_deps(lr._condition)
        for dep in lr._dependencies:
            collect_deps(dep)

        node_id = self.hashing_service.compute_node_instance_hash(task_def, lr, dep_map)

        # 4. Construct NodeIR
        # Flatten args and kwargs into a single 'inputs' dictionary
        inputs = {}
        for i, val in enumerate(transformed_args):
            inputs[str(i)] = val
        for k, val in transformed_kwargs.items():
            inputs[k] = val

        # Handle Constraints
        constraints = {}
        if lr._constraints:
            # We currently assume constraint values are literals.
            # TODO: Handle dynamic constraints (LazyResult in constraints)
            constraints = lr._constraints.requirements.copy()

        node_ir = NodeIR(
            id=node_id,
            name=task_def.name,
            task=task_def,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
        )
~~~~~

#### Acts 4: 更新 Expander 以物理化连接

修改 `Expander`，为 `Bleacher` 增加 `SIGNAL` 类型的端口，并在 `Builder` (后续计划中) 或 `Expander` 逻辑的配合下完成连接。由于 `Expander` 负责创建节点和内部连接，而 `Builder` 负责外部连接，实际上这里主要需要确保 `Bleacher` 生成了对应的端口定义，或者我们采取动态端口策略。

但 `Expander.expand_node` 目前定义了 `Bleacher` 的端口。我们需要根据 `NodeIR` 的新字段来动态增加端口定义。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        f_pre = BleachNode(
            id=f_pre_id,
~~~~~
~~~~~python.new
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )
        
        # Add ports for implicit dependencies (SIGNAL)
        for dep_id in node_ir.dependencies:
            # We use a naming convention for dependency ports
            port_name = f"wait_for_{dep_id}"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.SIGNAL, "Token"
            )
            
        # Add port for condition (SIGNAL/DATA)
        if node_ir.condition:
            port_name = "condition"
            bleacher_inputs[port_name] = PortDef(
                port_name, PortRole.SIGNAL, "Bool"
            )

        f_pre = BleachNode(
            id=f_pre_id,
~~~~~

#### Acts 5: 更新 Builder 以连接新端口

最后，我们需要更新 `Builder`，处理这些新暴露出来的端口的连线。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 4. Wire data dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert target_subgraph.bleacher is not None

            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
~~~~~
~~~~~python.new
        # 4. Wire dependencies between subgraphs
        for node_ir in graph_ir.nodes:
            target_subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert target_subgraph.bleacher is not None

            # 4.1 Data Dependencies (Arguments)
            for arg_name, source_ref in node_ir.inputs.items():
                # Case A: Reference to another node (Dependency)
                if isinstance(source_ref, str) and source_ref in subgraphs:
                    source_subgraph = subgraphs[source_ref]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                    # Wire Const -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=const_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )

        # 5. Wire Global Resources (The Loop)
~~~~~
~~~~~python.new
                    # Wire Const -> Bleacher
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=const_node_id,
                            source_port="out",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=arg_name,
                        )
                    )
            
            # 4.2 Sequence Dependencies (.after())
            for dep_id in node_ir.dependencies:
                if dep_id in subgraphs:
                    source_subgraph = subgraphs[dep_id]
                    # Help static analysis
                    assert source_subgraph.stainer is not None

                    port_name = f"wait_for_{dep_id}"
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=source_subgraph.stainer.id,
                            source_port="output",
                            target_node_id=target_subgraph.bleacher.id,
                            target_port=port_name,
                        )
                    )
            
            # 4.3 Condition (.run_if())
            if node_ir.condition and node_ir.condition in subgraphs:
                source_subgraph = subgraphs[node_ir.condition]
                # Help static analysis
                assert source_subgraph.stainer is not None

                physical_graph.channels.append(
                    Channel(
                        source_node_id=source_subgraph.stainer.id,
                        source_port="output",
                        target_node_id=target_subgraph.bleacher.id,
                        target_port="condition",
                    )
                )

        # 5. Wire Global Resources (The Loop)
~~~~~

### 下一步建议
我们已经完成了前端解析和后端物理连线的基础设施。下一步应该：
1.  **验证测试**: 编写集成测试，验证 `run_if` 和 `after` 构造的图是否能正确执行（物理层连线是否生效）。
2.  **完善 VM 逻辑**: 虽然现在连上了，但 `Bleacher` 目前可能只是傻傻地等待。对于 `Condition` 端口，我们需要在 `Bleacher` 或 `VM` 中实现特殊的处理逻辑：如果 `condition` 端口收到 False，则不应激发 Worker，而是直接进入 Skip 状态。这属于 Phase 2 的“收尾”或 Phase 3 的“物理层增强”。
