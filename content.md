## [WIP] debug(vm): 打印 function_map 以验证运行时映射

### 用户需求
在 E2E 测试中打印 `function_map` 的内容，以验证所有物理函数节点（Bleacher, Worker, Stainer）是否都已正确映射到其 Python 实现。

### 评论
我们已经确认了物理图的静态结构是正确的。现在，我们将矛头指向运行时。`function_map` 是连接物理节点 ID 和可执行代码的唯一桥梁。如果这里存在映射缺失，将直接导致节点无法执行，这与我们观察到的“幽灵节点”现象高度吻合。

### 目标
在 `test_e2e_vm_run.py` 中，`Reactor` 初始化之前，完整打印 `function_map` 的键。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/runtime-mapping #task/action/debug

---

### Script

#### Acts 1: 在测试中增加 function_map 打印逻辑

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
        elif node_id.endswith(".stain"):
            function_map[node_id] = standard_stainer
        # We don't need to map the observer for this test to keep it simple

    reactor = Reactor(physical_graph, memory, executor, function_map)
    reactor.prime()
~~~~~
~~~~~python.new
        elif node_id.endswith(".stain"):
            function_map[node_id] = standard_stainer
        # We don't need to map the observer for this test to keep it simple

    # --- DEBUG: Print Function Map ---
    print("\n--- [DEBUG] Function Map Keys ---")
    for key in sorted(function_map.keys()):
        print(f"  - Mapped: {key}")
    print("---------------------------------\n")
    # --- END DEBUG ---

    reactor = Reactor(physical_graph, memory, executor, function_map)
    reactor.prime()
~~~~~
