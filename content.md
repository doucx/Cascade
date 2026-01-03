## [WIP] fix(tests): 修复移除 Tag 后的测试和残留代码

### 错误分析

1.  **Tag 属性残留**: `Token` 和 `Channel` 的 `tag`/`tag_filter` 字段已被移除，但 `cascade-std` 的 `continuous.py` 以及多个单元测试（`test_visualizer.py`, `test_observer.py`, `test_stainer.py`）仍在使用它们，导致 `TypeError` 和 `AttributeError`。
2.  **Mock 对象属性缺失**: `standard_bleacher` 现在的逻辑依赖 `node.id` 来记录 Trace，但 `test_bleacher.py` 中的 Mock 对象未设置此属性，导致测试失败。

### 用户需求
修复因移除 Tag 机制而导致崩溃的单元测试，并清理 `continuous.py` 中残留的 Tag 引用。

### 评论
这是 Phase 1 重构的收尾工作。虽然我们修改了核心 Spec 和主要的 Discrete 资源逻辑，但 Continuous 资源和辅助测试代码也必须同步更新以保持一致性。特别是 `test_bleacher` 的 Mock 问题，反映了我们的 IC 逻辑对节点物理属性的依赖在增加。

### 目标
1.  修改 `packages/cascade-std/src/cascade/std/resource/continuous.py`，移除 `tag` 引用。
2.  修改 `packages/cascade-compiler/tests/unit/utils/test_visualizer.py`，适配无 Tag 的 `Channel`。
3.  修改 `packages/cascade-std/tests/unit/triad/test_bleacher.py`，为 Mock Node 添加 `id`。
4.  修改 `packages/cascade-std/tests/unit/triad/test_observer.py` 和 `test_stainer.py`，移除对 `tag` 的构造和断言。

### 基本原理
**一致性原则**：Spec 的变更是全局性的。任何组件（包括测试代码和次要功能模块）都不能假设已废弃的字段（如 `tag`）仍然存在。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/compiler #comp/tests #concept/topology #scope/core #task/domain/core #task/object/tests #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: [Std] 修复 `continuous.py` 中的 Tag 引用

更新连续型资源的分配逻辑，移除对 `tag` 的复制。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
    if ledger.available >= req_amount:
        ledger.available -= req_amount
        outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
    else:
        outputs["req_out"] = req_token
~~~~~
~~~~~python.new
    if ledger.available >= req_amount:
        ledger.available -= req_amount
        # Sovereignty: In the future, we should use trace-based routing here like discrete.py
        # For now, just remove the tag to fix the crash.
        outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        outputs["req_out"] = req_token
~~~~~

#### Acts 2: [Tests] 修复 `test_visualizer.py`

移除测试中 `Channel` 构造函数的 `tag_filter` 参数及相关断言。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/utils/test_visualizer.py
~~~~~
~~~~~python.old
    graph.channels.append(Channel("d1", "out", "task.bleach", "in"))
    graph.channels.append(
        Channel("task.bleach", "worker_input", "task.worker", "in", tag_filter="XYZ")
    )
    # Observability channel
    graph.channels.append(Channel("task.bleach", "obs_output", "bus", "in"))

    dumper = GraphDumper()
    dot_output = dumper.to_dot(graph)

    # Assertions
    assert "digraph G {" in dot_output
    assert "rankdir=LR;" in dot_output

    # Check Nodes
    assert '"d1" [label="Data1\\n(d1)\\nTokens: 1"' in dot_output
    assert 'shape="ellipse"' in dot_output
    assert '"task.bleach" [label="Bleacher\\n(task.bleach)"' in dot_output
    # Check heuristic coloring
    assert 'fillcolor="#ffccbc"' in dot_output  # Bleacher color

    # Check Edges
    assert '"d1" -> "task.bleach" [label="out -> in"' in dot_output
    assert '"task.bleach" -> "task.worker"' in dot_output
    assert 'label="worker_input -> in\\n[XYZ]"' in dot_output

    # Check Obs Edge Styling
    assert 'style="dashed"' in dot_output
~~~~~
~~~~~python.new
    graph.channels.append(Channel("d1", "out", "task.bleach", "in"))
    graph.channels.append(
        Channel("task.bleach", "worker_input", "task.worker", "in")
    )
    # Observability channel
    graph.channels.append(Channel("task.bleach", "obs_output", "bus", "in"))

    dumper = GraphDumper()
    dot_output = dumper.to_dot(graph)

    # Assertions
    assert "digraph G {" in dot_output
    assert "rankdir=LR;" in dot_output

    # Check Nodes
    assert '"d1" [label="Data1\\n(d1)\\nTokens: 1"' in dot_output
    assert 'shape="ellipse"' in dot_output
    assert '"task.bleach" [label="Bleacher\\n(task.bleach)"' in dot_output
    # Check heuristic coloring
    assert 'fillcolor="#ffccbc"' in dot_output  # Bleacher color

    # Check Edges
    assert '"d1" -> "task.bleach" [label="out -> in"' in dot_output
    assert '"task.bleach" -> "task.worker"' in dot_output
    assert 'label="worker_input -> in"' in dot_output

    # Check Obs Edge Styling
    assert 'style="dashed"' in dot_output
~~~~~

#### Acts 3: [Tests] 修复 `test_bleacher.py` 的 Mock 问题

为 Mock 对象设置 `id` 属性，以满足 `standard_bleacher` 的新逻辑。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node
~~~~~
~~~~~python.new
def create_mock_bleach_node(input_ports_config):
    node = MagicMock(spec=BleachNode)
    node.id = "test_node.bleach"  # Required for ID extraction logic
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node
~~~~~

#### Acts 4: [Tests] 修复 `test_observer.py` 和 `test_stainer.py` 的 Tag 引用

移除测试数据和断言中的 Tag 相关代码。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python.old
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}
~~~~~
~~~~~python.new
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", trace=end_trace)
    inputs = {"event_token": event_token}
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    assert output_token.tag == "default"
    assert output_token.trace["id"] == "task_A"
~~~~~
~~~~~python.new
    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    # Tag assertion removed
    assert output_token.trace["id"] == "task_A"
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    assert output_token.tag == "error"
    assert output_token.trace["end_ts"] == end_ts
~~~~~
~~~~~python.new
    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    # Tag assertion removed
    assert output_token.trace["end_ts"] == end_ts
~~~~~

### 下一步建议
这次修复应该覆盖了所有报告的测试失败。修复后，建议重新运行整个测试套件，特别是集成测试，以确保主权端口模型在端到端的场景中工作正常。如果一切顺利，Phase 1 就正式完成了。
