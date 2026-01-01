好的，我们现在进入最关键的**第三步：修正编译器链的后端与执行器**。

这一步将打通“身份传递”的最后一个环节：让 `Backend` 将 `canonical_code_structure_hash` 传递给运行时的物理节点，并让 `PhysicsExecutor` 最终使用这个哈希值从 `symbol_table` 中精准地提取出可执行函数。

同时，我将顺便清理 `backend.py` 中那些被 Linter 标记为不合规的本地哈希变量名，确保它们符合 v3.0 公理。

## [WIP] refactor(vm): Bridge the identity gap in Backend and PhysicsExecutor

### 用户需求
修正物理引擎的链接机制。确保 `Backend` 能够传递 `canonical_code_structure_hash`，并让 `PhysicsExecutor` 使用该哈希进行符号查找。同时，根据 v3.0 公理重构 `backend.py` 中的本地哈希变量命名。

### 评论
这是解决“死锁”和“链接失败”的临门一脚。通过在 `PhysicsFuncNode` 中明确引入 `canonical_code_structure_hash`，我们彻底废除了使用 `name` 这种模糊字段进行底层逻辑链接的“黑巧”。这不仅解决了当前的测试失败，更在物理引擎和编译器之间建立了稳固、类型安全的身份契约。

### 目标
1.  **修改 `PhysicsFuncNode`**: 在拓扑规范中添加 `canonical_code_structure_hash` 字段。
2.  **修改 `Backend`**: 在编译过程中，将 `NodeIR` 的规范哈希无损传递给 `PhysicsFuncNode`。
3.  **重构命名**: 将 `backend.py` 中的 `func_hash`, `data_slot_hash` 等重命名为符合 v3.0 公理的长命名。
4.  **修改 `PhysicsExecutor`**: 将符号查找逻辑从 `node.name` 切换为 `node.canonical_code_structure_hash`。

### 基本原理
我们正在消除“身份危机”的最后病灶。在物理模型中，`name` 应当仅用于人类观察。通过引入专用的 `canonical_code_structure_hash` 字段进行符号表链接，我们实现了“执行身份”与“观察身份”的彻底解耦。使用 v3.0 的长命名规范重构变量，则进一步确保了编译器内部逻辑的自文档化和零歧义。

### 标签
#intent/refine #flow/ready #priority/critical #comp/vm #comp/compiler #scope/core #ai/instruct #task/domain/testing #task/object/identity-bridge #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新拓扑规范 `PhysicsFuncNode`

首先，为物理函数节点添加用于链接的规范哈希字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    # The stable, linkable identity used to look up the executable code in the symbol table.
    canonical_code_structure_hash: str
    name: str
    # Map input argument names to the source DataNode hash
~~~~~

#### Acts 2: 修正 `Backend` 的编译逻辑与变量命名

现在，更新 `Backend` 以传递规范哈希，并同时清理不规范的本地变量名。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_node(self, node_ir: NodeIR):
        func_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=func_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[func_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        data_slot_hash = self._compute_data_slot_hash(func_hash, "result")
        self._func_output_map[func_hash] = data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=func_hash,
        )
        self._data_nodes[data_slot_hash] = d_node
~~~~~
~~~~~python.new
    def _process_node(self, node_ir: NodeIR):
        current_node_instance_hash = node_ir.current_node_instance_hash

        f_node = PhysicsFuncNode(
            current_node_instance_hash=current_node_instance_hash,
            canonical_code_structure_hash=node_ir.definition.canonical_code_structure_hash,
            name=node_ir.definition.name,
            inputs={},
            sink_id=None,  # Explicitly set sink_id to None for regular nodes
        )
        self._func_nodes[current_node_instance_hash] = f_node

        for i, val in enumerate(node_ir.args):
            self._process_literal(f_node, str(i), val)

        for k, val in node_ir.kwargs.items():
            self._process_literal(f_node, k, val)

        current_data_slot_hash = self._compute_data_slot_hash(current_node_instance_hash, "result")
        self._func_output_map[current_node_instance_hash] = current_data_slot_hash

        d_node = PhysicsDataNode(
            current_data_slot_hash=current_data_slot_hash,
            name=f"{node_ir.definition.name}.output",
            producer_node_instance_hash=current_node_instance_hash,
        )
        self._data_nodes[current_data_slot_hash] = d_node
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            source_func_hash = edge.source_node_instance_hash
            target_func_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            source_data_hash = self._func_output_map.get(source_func_hash)

            if not source_data_hash:
                raise RuntimeError(
                    f"Source node {source_func_hash} not found in output map"
                )

            target_func_node = self._func_nodes.get(target_func_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = source_data_hash
~~~~~
~~~~~python.new
    def _process_data_edges(self):
        for edge in self._graph.edges:
            if edge.kind != EdgeKind.DATA:
                continue

            current_source_node_instance_hash = edge.source_node_instance_hash
            current_target_node_instance_hash = edge.target_node_instance_hash
            arg_name = edge.target_arg

            current_source_data_slot_hash = self._func_output_map.get(current_source_node_instance_hash)

            if not current_source_data_slot_hash:
                raise RuntimeError(
                    f"Source node {current_source_node_instance_hash} not found in output map"
                )

            target_func_node = self._func_nodes.get(current_target_node_instance_hash)
            if target_func_node:
                target_func_node.inputs[arg_name] = current_source_data_slot_hash
~~~~~

#### Acts 3: 修正 `PhysicsExecutor` 的查找逻辑

最后，修改执行器，让它使用规范哈希从符号表中链接函数。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/executors/physics.py
~~~~~
~~~~~python.old
        try:
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )
~~~~~
~~~~~python.new
        try:
            # 1. Linking: Use the canonical code structure hash to find the executable logic.
            # This decouples the node's human-readable 'name' from its functional identity.
            func = self._symbol_table.get(node.canonical_code_structure_hash)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    f"(hash: {node.canonical_code_structure_hash}) not found in symbol table."
                )
~~~~~

### 下一步建议
我们已经完成了编译器链和执行器的重构，建立了清晰的“身份桥梁”。

接下来是**第四步：全面清理与公理验证**。
目前还有 `backend.py` 中的 `const_hash`, `root_node_hash` 等本地变量名，以及 `ReflectionAnalyzer` 中的方法参数名需要修正。

我建议再次运行我们的 `scripts/lint_hash_names.py`，查看剩余的违规项，并逐一消除它们，直到代码库完全符合 v3.0 公理。这将确保我们的重构不仅解决了逻辑问题，还在质量和规范上达到了最高标准。
