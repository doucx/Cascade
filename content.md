## [WIP] fix: 修复 TCO 测试中断言逻辑的脆弱性

### 用户需求
修复 `test_backend_tco.py` 中的测试失败。

### 错误分析
测试失败 `AssertionError: assert 'default' == 'ping'` 是由于测试代码中的查询逻辑过于脆弱。
编译器后端正确地生成了两个通道：
1.  **默认通道** (`tag="default"`): 由 `_process_node` 创建，用于常规数据流。
2.  **跳转通道** (`tag="ping"`): 由 `_process_jumps` 创建，用于 TCO。

测试代码使用 `next((c for c in topology.channels if c.source_node_instance_hash == "Ping"), None)` 获取了列表中的第一个通道（即默认通道），并断言它是跳转通道，导致失败。

### 解决方案
修改测试中的查询逻辑，使其根据 `source_node_instance_hash` **和** `tag_filter` 精确查找通道，或者在获取后验证是否包含目标通道。更稳健的做法是直接查找目标 `tag` 的通道。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct
#task/domain/compiler #task/object/tco-backend #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修正测试断言

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_tco.py
~~~~~
~~~~~python.old
    topology = Backend.compile(graph_ir)
    
    # Verify Channel Ping -> Pong
    c1 = next((c for c in topology.channels if c.source_node_instance_hash == "Ping"), None)
    assert c1 is not None
    assert c1.tag_filter == "ping"
    assert c1.target_data_slot_hash == topology.func_nodes["Pong"].inputs["y"]
    
    # Verify Channel Pong -> Ping
    c2 = next((c for c in topology.channels if c.source_node_instance_hash == "Pong"), None)
    assert c2 is not None
    assert c2.tag_filter == "pong"
    assert c2.target_data_slot_hash == topology.func_nodes["Ping"].inputs["x"]
~~~~~
~~~~~python.new
    topology = Backend.compile(graph_ir)
    
    # Verify Channel Ping -> Pong
    # Note: We must filter by tag because there is also a default output channel
    c1 = next((c for c in topology.channels if c.source_node_instance_hash == "Ping" and c.tag_filter == "ping"), None)
    assert c1 is not None, "Channel Ping->Pong with tag 'ping' not found"
    assert c1.target_data_slot_hash == topology.func_nodes["Pong"].inputs["y"]
    
    # Verify Channel Pong -> Ping
    c2 = next((c for c in topology.channels if c.source_node_instance_hash == "Pong" and c.tag_filter == "pong"), None)
    assert c2 is not None, "Channel Pong->Ping with tag 'pong' not found"
    assert c2.target_data_slot_hash == topology.func_nodes["Ping"].inputs["x"]
~~~~~

### 下一步建议
现在测试应该通过了。请运行测试。如果通过，我们将完成 TCO 的编译器支持（阶段 3.4），并正式关闭第三阶段。接下来将是 **第四阶段：Engine 重构 (Phase 4)**，我们将使用这个新编译器和 VM 来驱动引擎。
