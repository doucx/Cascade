简要回答：
这是一个针对 "The Great Renaming" 的大规模重构计划。我们将更新 `serialize.py` 以匹配新的 JSON 键名规范，并系统性地修复所有因 `Node.structural_id` 和 `NodeIR.id` 废弃而导致的测试失败。

## [WIP] refactor: 全局重命名 ID 字段以符合哈希命名公理

### 错误分析
当前的测试失败是由于 `cascade-spec` 更新了核心数据模型（废弃了 `id` 和 `structural_id`），但测试代码和部分序列化逻辑仍在使用旧符号。
1.  **AttributeError**: 测试代码试图访问已不存在的 `node.id` 或 `node.structural_id`。
2.  **TypeError**: 测试代码在构造 `NodeIR` 时传递了非法的 `id` 参数。
3.  **KeyError**: 序列化/反序列化逻辑或测试断言使用了旧的字典键。

### 用户需求
1.  将所有 `NodeIR.id` 和 `Node.structural_id` 的引用更新为 `current_node_instance_hash`。
2.  确保序列化输出的 JSON 键名也遵循新规范。
3.  修复所有受影响的测试用例。

### 评论
这是一次必要的“大扫除”。虽然修改范围很广，但逻辑非常机械且清晰。严格执行哈希命名公理将消除未来的歧义。

### 目标
使所有下游组件（Compiler, Graph, Engine）的测试代码与新的 Spec 定义对齐，确保测试通过。

### 基本原理
通过 `patch_file` 逐个修正受影响的文件。对于 `serialize.py`，我们将改变其数据交换格式，这在当前开发阶段是可以接受的。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/core #scope/core #ai/instruct #task/domain/core #task/object/identifier #task/action/rename #task/state/continue

---

### Script

#### Acts 1: 更新序列化逻辑 (Serialization)

首先更新 `cascade-graph` 的序列化模块，使其产生的字典和 JSON 使用新的键名 `current_node_instance_hash` 而非 `structural_id`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "structural_id": node.current_node_instance_hash,
        "name": node.name,
        "node_type": node.node_type,
~~~~~
~~~~~python.new
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "current_node_instance_hash": node.current_node_instance_hash,
        "name": node.name,
        "node_type": node.node_type,
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    if node_type == "map":
        node = MapNode(
            current_node_instance_hash=data["structural_id"],
            definition=stub_def,
            node_type="map",
~~~~~
~~~~~python.new
    if node_type == "map":
        node = MapNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="map",
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            current_node_instance_hash=data["structural_id"],
            definition=stub_def,
            node_type="param",
~~~~~
~~~~~python.new
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="param",
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    else:
        # Default to TaskNode
        node = TaskNode(
            current_node_instance_hash=data["structural_id"],
            definition=stub_def,
            node_type="task",
~~~~~
~~~~~python.new
    else:
        # Default to TaskNode
        node = TaskNode(
            current_node_instance_hash=data["current_node_instance_hash"],
            definition=stub_def,
            node_type="task",
~~~~~

#### Acts 2: 修复 Cascade Spec 测试

修复 `cascade-spec` 中关于 IR 模型的单元测试，替换 `id` 为 `current_node_instance_hash`。

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~python.old
    node = NodeIR(current_node_instance_hash="node_1", definition=task_def, kwargs={"x": 1, "y": "hello"})

    edge = EdgeIR(source_node_instance_hash="node_1", target_node_instance_hash="node_2", target_arg="data")

    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].id == "node_1"
    assert graph.edges[0].source_node_instance_hash == "node_1"
    assert graph.meta["version"] == "1.0"


def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(name="test_task", args=[arg_def], fingerprint=fp)

    node = NodeIR(current_node_instance_hash="n1", definition=task_def, kwargs={"val": 42})

    graph = GraphIR(nodes=[node], edges=[])

    # Convert to dictionary using dataclasses.asdict
    data = asdict(graph)

    # Verify key fields
    assert data["nodes"][0]["id"] == "n1"
    assert data["nodes"][0]["kwargs"]["val"] == 42
    assert data["nodes"][0]["definition"]["name"] == "test_task"
    assert data["nodes"][0]["definition"]["args"][0]["kind"] == "POSITIONAL_OR_KEYWORD"

    # Verify JSON serialization compatibility
    json_str = json.dumps(data)
    loaded = json.loads(json_str)

    assert loaded["nodes"][0]["id"] == "n1"
~~~~~
~~~~~python.new
    node = NodeIR(current_node_instance_hash="node_1", definition=task_def, kwargs={"x": 1, "y": "hello"})

    edge = EdgeIR(source_node_instance_hash="node_1", target_node_instance_hash="node_2", target_arg="data")

    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].current_node_instance_hash == "node_1"
    assert graph.edges[0].source_node_instance_hash == "node_1"
    assert graph.meta["version"] == "1.0"


def test_ir_serialization_roundtrip():
    """Verify that IR structures can be serialized to and from JSON."""
    fp = Fingerprint()
    fp["current_code_structure_hash"] = "test_hash"

    arg_def = ArgumentDef(name="arg1", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
    task_def = TaskDef(name="test_task", args=[arg_def], fingerprint=fp)

    node = NodeIR(current_node_instance_hash="n1", definition=task_def, kwargs={"val": 42})

    graph = GraphIR(nodes=[node], edges=[])

    # Convert to dictionary using dataclasses.asdict
    data = asdict(graph)

    # Verify key fields
    assert data["nodes"][0]["current_node_instance_hash"] == "n1"
    assert data["nodes"][0]["kwargs"]["val"] == 42
    assert data["nodes"][0]["definition"]["name"] == "test_task"
    assert data["nodes"][0]["definition"]["args"][0]["kind"] == "POSITIONAL_OR_KEYWORD"

    # Verify JSON serialization compatibility
    json_str = json.dumps(data)
    loaded = json.loads(json_str)

    assert loaded["nodes"][0]["current_node_instance_hash"] == "n1"
~~~~~

#### Acts 3: 修复 Cascade Compiler 测试 (Backend)

修复 Backend 相关测试，移除 `id` 引用。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~
~~~~~python.old
    task_def = _create_dummy_task_def("task_A")
    node = NodeIR(current_node_instance_hash="A", definition=task_def, kwargs={"x": 1, "y": "hello"})
    
    ir = GraphIR(nodes=[node], edges=[])
~~~~~
~~~~~python.new
    task_def = _create_dummy_task_def("task_A")
    node = NodeIR(current_node_instance_hash="A", definition=task_def, kwargs={"x": 1, "y": "hello"})
    
    ir = GraphIR(nodes=[node], edges=[])
~~~~~
