## [WIP] refactor: 修复测试套件中的遗留标识符引用

### 用户需求
LibCST 脚本成功完成了类定义和大部分属性访问的重命名，但正如预期，部分复杂的测试断言（如字典键访问、下标对象属性访问）未能被启发式规则捕获。我们需要手动修复这些遗留问题，使测试套件通过。

### 评论
错误日志揭示了一个环境问题：`pytest` 似乎加载了 `site-packages` 中的旧版本 `cascade-compiler` 代码（导致 `NodeIR.__init__` 报错），同时加载了新修改的 `cascade-spec` 代码（导致 `AttributeError`）。这种版本不匹配加剧了报错数量。虽然我们无法直接修复用户的环境，但我们可以通过设置 `PYTHONPATH` 强制测试使用我们刚修改的源码。

本计划专注于修复源码中确定的断言错误。

### 目标
1.  修复 `packages/cascade-spec/tests/unit/test_ir_models.py` 中的断言，将 `id` 替换为 `current_node_instance_hash`。
2.  确保 `packages/cascade-compiler` 中的代码与新命名一致。
3.  通过设置 `PYTHONPATH` 运行测试，以验证源码的正确性。

### 基本原理
-   **断言修正**: 测试代码中的 `graph.nodes[0].id` 和 `data["nodes"][0]["id"]` 由于 AST 结构的复杂性（下标访问和字符串字面量）被脚本跳过，必须手动修正。
-   **环境隔离**: 使用 `PYTHONPATH=packages/cascade-spec/src:packages/cascade-compiler/src:packages/cascade-graph/src` 运行测试，确保加载的是当前修改过的代码，而非系统安装的旧包。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/identifier-refactor #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 IR 模型测试中的断言

我们将修复 `test_ir_models.py` 中所有过时的 `id` 和 `source_id` 引用。

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~old
    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].id == "node_1"
    assert graph.edges[0].source_node_instance_hash == "node_1"
    assert graph.meta["version"] == "1.0"
~~~~~
~~~~~new
    graph = GraphIR(nodes=[node], edges=[edge], meta={"version": "1.0"})

    assert graph.nodes[0].current_node_instance_hash == "node_1"
    assert graph.edges[0].source_node_instance_hash == "node_1"
    assert graph.meta["version"] == "1.0"
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~old
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
~~~~~new
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

### 下一步建议
如果 `test_ir_models.py` 通过，我们将继续检查并修复其他测试文件（如 `backend.py` 相关的测试），并最终运行完整测试套件。如果仍然报错，我们将根据报错信息进一步定位遗漏点。
