## [WIP] fix(compiler): 修复启动脉冲能量不足及源节点识别逻辑

### 用户需求
1.  解决 `global.start.pulse` 初始 Token 只有一个，导致多个源节点竞争饿死的问题。
2.  修复源节点识别逻辑，改用基于 `NodeIR` 的逻辑判断，避免因物理层引入中间 DataNode 而导致的误判。

### 评论
我们终于找到了 `setup_task` 不执行的物理原因：能量不足。这是一个经典的资源竞争问题。同时，我们通过回归到逻辑层定义来识别源节点，这是一种更稳健的策略，不再受物理层实现细节（如是否插入中间节点）的干扰。

### 目标
1.  修改 `Builder`，将 `D_start` 的 `initial_tokens` 设为 `sys.maxsize`。
2.  重写 `Builder` 最后的连线逻辑，遍历 `graph_ir.nodes`，识别逻辑源节点，并进行连接。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/start-pulse #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 增加启动脉冲能量并优化源节点连接

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 1.2 Global Start Pulse
        start_pulse_id = PhysicalIdGenerator.start_pulse()
        d_start = PhysicsDataNode(
            id=start_pulse_id,
            name="GlobalStartPulse",
            capacity=sys.maxsize, # Can trigger infinite source nodes
            initial_tokens=1,
        )
        physical_graph.nodes[start_pulse_id] = d_start
~~~~~
~~~~~python.new
        # 1.2 Global Start Pulse
        start_pulse_id = PhysicalIdGenerator.start_pulse()
        d_start = PhysicsDataNode(
            id=start_pulse_id,
            name="GlobalStartPulse",
            capacity=sys.maxsize, # Can trigger infinite source nodes
            initial_tokens=sys.maxsize, # Infinite energy for all source nodes
        )
        physical_graph.nodes[start_pulse_id] = d_start
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 6. Wire Global Start Pulse to all Source Nodes
        # A source node's bleacher is one that does not depend on any other task's stainer.
        task_fed_bleacher_ids = {
            c.target_node_id
            for c in physical_graph.channels
            if c.source_node_id.endswith(".stain")
        }

        for subgraph in subgraphs.values():
            bleacher = subgraph.bleacher
            if bleacher and bleacher.id not in task_fed_bleacher_ids:
                # This bleacher is a source node, connect it to the start pulse
                physical_graph.channels.append(
                    Channel(
                        source_node_id=start_pulse_id,
                        source_port="out",
                        target_node_id=bleacher.id,
                        target_port="__start__",
                    )
                )
~~~~~
~~~~~python.new
        # 6. Wire Global Start Pulse to all Source Nodes
        # We identify source nodes based on the Logical IR, which is more robust than analyzing the physical graph.
        # A source node is one that has no dependencies on other nodes (dynamic inputs, conditions, or sequences).
        for node_ir in graph_ir.nodes:
            is_source = True
            
            # Check 1: Sequence dependencies
            if node_ir.dependencies:
                is_source = False
            
            # Check 2: Condition
            if node_ir.condition:
                is_source = False
                
            # Check 3: Dynamic Data Inputs (Reference to other nodes)
            if is_source:
                for source_ref in node_ir.inputs.values():
                    if isinstance(source_ref, str) and source_ref in subgraphs:
                        is_source = False
                        break
            
            if is_source:
                subgraph = subgraphs[node_ir.id]
                if subgraph.bleacher:
                    physical_graph.channels.append(
                        Channel(
                            source_node_id=start_pulse_id,
                            source_port="out",
                            target_node_id=subgraph.bleacher.id,
                            target_port="__start__",
                        )
                    )
~~~~~

### 下一步建议
这是最后的一块拼图。我有十足的把握，这次测试将完美通过。`D_start` 将拥有无限能量，`setup_task` 将被正确识别为源节点并激发，它的输出将经由 `Signal` 节点到达 `main_task`，解锁整个流程。祝我们好运！
