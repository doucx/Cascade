简要回答
我将生成一个修复计划，重点是更新测试代码以符合哈希命名公理，并修正因 schema 变更导致的测试失败。

## [WIP] fix: 对齐测试代码与哈希命名公理及 Schema 变更

### 用户需求
修复因实施 "Hash Naming Axiom" (d3-axiom-arch-stable-identifiers) 而导致的 `cascade-compiler`、`cascade-spec` 和 `cascade-vm` 中的测试失败和 Linter 违规。这包括：
1. 更新仅在测试中使用的辅助函数，使其通过新的 `TaskDef` 和 `PhysicsFuncNode` 构造参数。
2. 将测试中使用的哈希变量名重构为符合四段式命名规范的格式。
3. 确保运行时物理模型 (`FuncNode`) 携带必要的身份哈希。

### 评论
当前的破坏是实施严格命名规范后的常见阵痛。测试代码作为系统的第一次使用者，必须严格遵守新的公理。将 `fingerprint` 替换为 `canonical_code_structure_hash` 是从“内容完整性”向“身份链接”转变的关键一步。

### 目标
1.  **Linter通过**: 消除 `test_backend_tco.py` 和 `test_backend_topology.py` 中的所有哈希命名违规。
2.  **Schema对齐**: 更新所有测试辅助函数以使用 `TaskDef(canonical_code_structure_hash=...)` 而非 `fingerprint`。
3.  **运行时修复**: 更新 `PhysicsFuncNode` (Spec) 和 `FuncNode` (Runtime) 的定义与实例化，确保身份哈希在整个系统中流动。

### 基本原理
1.  **测试辅助函数**: 测试中的 Mock 数据结构必须反映真实的 IR 结构。`TaskDef` 现在要求明确的规范哈希，而不是通用的指纹对象。
2.  **变量重命名**: 为了通过 `lint_hash_names.py`，测试变量必须遵循 `[State]_[Source]_[Object]_hash` 格式。
3.  **物理节点更新**: 错误日志显示 `FuncNode` 缺少 `canonical_code_structure_hash` 属性，这表明运行时执行器试图根据此哈希进行链接，但基础物理对象尚未更新以承载此信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/spec #scope/core #ai/instruct #task/domain/testing #task/object/hash-naming #task/action/compliance #task/state/begin

---

### Script

#### Acts 1: 修复 Spec 模型与测试
更新 `cascade-spec` 中的物理节点定义和相关测试，以支持新的哈希字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def __init__(
        self, name: str, resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
~~~~~
~~~~~python.new
    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str = "",
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.canonical_code_structure_hash = canonical_code_structure_hash
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~python.old
    # This test will fail until the models are created.
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    task_def = TaskDef(name="test_task", args=[], fingerprint=fp)

    node = NodeIR(
~~~~~
~~~~~python.new
    # This test will fail until the models are created.
    task_def = TaskDef(
        name="test_task",
        args=[],
        canonical_code_structure_hash="canonical_code_structure_hash_test",
    )

    node = NodeIR(
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~python.old
def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(name="test_task", args=[arg_def], fingerprint=fp)

    node = NodeIR(
~~~~~
~~~~~python.new
def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(
        name="test_task",
        args=[arg_def],
        canonical_code_structure_hash="canonical_code_structure_hash_test",
    )

    node = NodeIR(
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/topology/test_bipartite_graph_schema.py
~~~~~
~~~~~python.old
    # PhysicsFuncNode: Represents a computation instance (The "Verb")
    f_node = PhysicsFuncNode(
        current_node_instance_hash="func_inst_abc", name="calculate_metrics"
    )
    assert is_dataclass(f_node)
    assert f_node.current_node_instance_hash == "func_inst_abc"
~~~~~
~~~~~python.new
    # PhysicsFuncNode: Represents a computation instance (The "Verb")
    f_node = PhysicsFuncNode(
        current_node_instance_hash="func_inst_abc",
        canonical_code_structure_hash="canonical_code_structure_hash_metrics",
        name="calculate_metrics",
    )
    assert is_dataclass(f_node)
    assert f_node.current_node_instance_hash == "func_inst_abc"
~~~~~

#### Acts 2: 修复 Compiler 测试辅助函数
更新 `cascade-compiler` 中用于创建模拟节点的辅助函数，并同时修复哈希变量命名违规。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_tco.py
~~~~~
~~~~~python.old
def _create_dummy_node(node_id: str, arg_names: List[str] = None) -> NodeIR:
    """Helper to create a minimal NodeIR for TCO tests."""
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})

    args = []
    if arg_names:
        for name in arg_names:
            args.append(ArgumentDef(name=name, kind=ArgumentKind.POSITIONAL_OR_KEYWORD))

    task_def = TaskDef(name=node_id, args=args, fingerprint=fp)
    # We use the node_id as the instance hash for clarity in tests
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~
~~~~~python.new
def _create_dummy_node(node_id: str, arg_names: List[str] = None) -> NodeIR:
    """Helper to create a minimal NodeIR for TCO tests."""
    args = []
    if arg_names:
        for name in arg_names:
            args.append(ArgumentDef(name=name, kind=ArgumentKind.POSITIONAL_OR_KEYWORD))

    task_def = TaskDef(
        name=node_id,
        args=args,
        canonical_code_structure_hash=f"canonical_code_structure_hash_{node_id}",
    )
    # We use the node_id as the instance hash for clarity in tests
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_tco.py
~~~~~
~~~~~python.old
    # Verify Input Slot (DataNode) for 'n' exists
    # The compiler should have created a DataNode for the input 'n'
    assert "n" in func_node.inputs
    input_data_hash = func_node.inputs["n"]
    assert input_data_hash in topology.data_nodes

    # Verify Feedback Channel
~~~~~
~~~~~python.new
    # Verify Input Slot (DataNode) for 'n' exists
    # The compiler should have created a DataNode for the input 'n'
    assert "n" in func_node.inputs
    current_input_slot_hash = func_node.inputs["n"]
    assert current_input_slot_hash in topology.data_nodes

    # Verify Feedback Channel
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_tco.py
~~~~~
~~~~~python.old
    # Verify Feedback Channel
    # We look for a channel that:
    # - originates from 'counter'
    # - targets the input slot of 'counter' (input_data_hash)
    # - has tag_filter="loop"

    feedback_channel = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == "counter"
            and c.target_data_slot_hash == input_data_hash
            and c.tag_filter == "loop"
        ),
        None,
    )
~~~~~
~~~~~python.new
    # Verify Feedback Channel
    # We look for a channel that:
    # - originates from 'counter'
    # - targets the input slot of 'counter' (current_input_slot_hash)
    # - has tag_filter="loop"

    feedback_channel = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == "counter"
            and c.target_data_slot_hash == current_input_slot_hash
            and c.tag_filter == "loop"
        ),
        None,
    )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_tco.py
~~~~~
~~~~~python.old
    # Verify targets
    # chan_b should point to B's input
    b_input_hash = topology.func_nodes["B"].inputs["val"]
    assert chan_b.target_data_slot_hash == b_input_hash

    # chan_c should point to C's input
    c_input_hash = topology.func_nodes["C"].inputs["val"]
    assert chan_c.target_data_slot_hash == c_input_hash
~~~~~
~~~~~python.new
    # Verify targets
    # chan_b should point to B's input
    current_b_input_slot_hash = topology.func_nodes["B"].inputs["val"]
    assert chan_b.target_data_slot_hash == current_b_input_slot_hash

    # chan_c should point to C's input
    current_c_input_slot_hash = topology.func_nodes["C"].inputs["val"]
    assert chan_c.target_data_slot_hash == current_c_input_slot_hash
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for testing."""
    # We use the node_id as the structure hash for simplicity in tests
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})
    task_def = TaskDef(name=node_id, args=[], fingerprint=fp)
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~
~~~~~python.new
def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for testing."""
    # We use the node_id as the structure hash for simplicity in tests
    task_def = TaskDef(
        name=node_id,
        args=[],
        canonical_code_structure_hash=f"canonical_code_structure_hash_{node_id}",
    )
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    func_node_a = topology.func_nodes["A"]
    assert "x" in func_node_a.inputs
    assert "y" in func_node_a.inputs

    data_hash_x = func_node_a.inputs["x"]
    data_hash_y = func_node_a.inputs["y"]

    # Verify DataNodes exist
    assert data_hash_x in topology.data_nodes
    assert data_hash_y in topology.data_nodes

    # Verify they are marked as Constants (no producer)
    # The convention for constants is producer_node_instance_hash being empty or special
    assert topology.data_nodes[data_hash_x].producer_node_instance_hash == "const"
    assert topology.data_nodes[data_hash_y].producer_node_instance_hash == "const"

    # Verify Values are captured
    # We expect BipartiteGraph to have an 'initial_values' map
    assert hasattr(topology, "initial_values"), (
        "BipartiteGraph must hold initial values for constants"
    )
    assert topology.initial_values[data_hash_x] == 1
    assert topology.initial_values[data_hash_y] == "hello"
~~~~~
~~~~~python.new
    func_node_a = topology.func_nodes["A"]
    assert "x" in func_node_a.inputs
    assert "y" in func_node_a.inputs

    current_x_data_slot_hash = func_node_a.inputs["x"]
    current_y_data_slot_hash = func_node_a.inputs["y"]

    # Verify DataNodes exist
    assert current_x_data_slot_hash in topology.data_nodes
    assert current_y_data_slot_hash in topology.data_nodes

    # Verify they are marked as Constants (no producer)
    # The convention for constants is producer_node_instance_hash being empty or special
    assert (
        topology.data_nodes[current_x_data_slot_hash].producer_node_instance_hash
        == "const"
    )
    assert (
        topology.data_nodes[current_y_data_slot_hash].producer_node_instance_hash
        == "const"
    )

    # Verify Values are captured
    # We expect BipartiteGraph to have an 'initial_values' map
    assert hasattr(topology, "initial_values"), (
        "BipartiteGraph must hold initial values for constants"
    )
    assert topology.initial_values[current_x_data_slot_hash] == 1
    assert topology.initial_values[current_y_data_slot_hash] == "hello"
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    # Get the input DataNode hash for both
    input_hash_b = func_b.inputs["dep_b"]
    input_hash_c = func_c.inputs["dep_c"]

    # Critical: They MUST be the same DataNode (Structural Sharing)
    assert input_hash_b == input_hash_c, "Fan-out should reuse the same source DataNode"

    # Verify that DataNode is produced by A
    data_node = topology.data_nodes[input_hash_b]
~~~~~
~~~~~python.new
    # Get the input DataNode hash for both
    current_b_input_slot_hash = func_b.inputs["dep_b"]
    current_c_input_slot_hash = func_c.inputs["dep_c"]

    # Critical: They MUST be the same DataNode (Structural Sharing)
    assert (
        current_b_input_slot_hash == current_c_input_slot_hash
    ), "Fan-out should reuse the same source DataNode"

    # Verify that DataNode is produced by A
    data_node = topology.data_nodes[current_b_input_slot_hash]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    # 5. Assert that Result Emitter is connected to the graph's output
    # Find the output data slot of the original root node 'A'
    output_of_a_hash = next(
        c.target_data_slot_hash
        for c in topology.channels
        if c.source_node_instance_hash == "A" and c.kind == ChannelKind.DATA
    )
    assert "result" in result_emitter.inputs, (
        "Result emitter must have a 'result' input"
    )
    assert result_emitter.inputs["result"] == output_of_a_hash
~~~~~
~~~~~python.new
    # 5. Assert that Result Emitter is connected to the graph's output
    # Find the output data slot of the original root node 'A'
    current_a_output_slot_hash = next(
        c.target_data_slot_hash
        for c in topology.channels
        if c.source_node_instance_hash == "A" and c.kind == ChannelKind.DATA
    )
    assert "result" in result_emitter.inputs, (
        "Result emitter must have a 'result' input"
    )
    assert result_emitter.inputs["result"] == current_a_output_slot_hash
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_optimizer.py
~~~~~
~~~~~python.old
def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for topology tests."""
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})
    task_def = TaskDef(name=node_id, args=[], fingerprint=fp)
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~
~~~~~python.new
def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for topology tests."""
    task_def = TaskDef(
        name=node_id,
        args=[],
        canonical_code_structure_hash=f"canonical_code_structure_hash_{node_id}",
    )
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)
~~~~~

#### Acts 3: 修复 Frontend 测试
更新 `test_frontend.py` 以移除对 `fingerprint` 的访问，并使用新的 `canonical_code_structure_hash` 验证。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.kwargs["x"] == 10

    # 4. Axiom Check: Enforce Long Hash Naming
    # We don't check the value, but the KEY must be the long form.
    fp = node.definition.fingerprint
    assert "current_code_structure_hash" in fp
    # Ensure no short names are present
    assert "hash" not in fp
    assert "id" not in fp
    assert "structure_hash" not in fp
~~~~~
~~~~~python.new
    node = ir.nodes[0]
    assert node.definition.name == "simple_task"
    assert node.kwargs["x"] == 10

    # 4. Axiom Check: Enforce Long Hash Naming for Identity
    # Check that canonical hash is present and looks like a hash
    assert node.definition.canonical_code_structure_hash
    # We can also verify it's not a short name or empty
    assert len(node.definition.canonical_code_structure_hash) >= 8
~~~~~

### 下一步建议
实施完此计划后，重新运行 `pytest` 和 `lint_hash_names.py`。所有的 Linter 错误和提及的 19 个测试失败都应该得到解决。如果 `cascade-vm` 的测试仍然失败，请重点检查 Executor 与新 `FuncNode` 定义的兼容性。
