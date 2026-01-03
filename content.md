## [WIP] fix(compiler): 优化 Builder 的源节点识别逻辑

### 用户需求
修复 `Builder` 中识别源节点的逻辑缺陷。当前逻辑将由常量数据节点 (`D_const`) 驱动的任务错误地排除在源节点之外，导致它们无法接收到全局启动脉冲。

### 评论
通过将源节点的定义精确化为“不依赖于任何其他任务（`.stain` 节点）输出的节点”，我们解决了 `setup_task` 未被执行的根本原因。这个修复将确保所有真正的源节点，无论它们是否有常量输入，都能被正确地连接到全局启动脉冲，从而保证了整个计算图的正确启动。

### 目标
修改 `packages/cascade-compiler/src/cascade/compiler/backend/builder.py` 中的启动脉冲连接逻辑，使其只排除那些被其他任务的 `Stainer` 节点连接的 `Bleacher` 节点。

### 基本原理
一个任务是否是“源头”，取决于它是否需要等待其他任务完成，而不是它是否有输入。常量输入是编译时就绪的初始条件，不构成任务间的时序依赖。因此，在决定是否连接启动脉冲时，我们必须只考虑来自其他任务 (`.stain` 节点) 的连接。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/source-node-activation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 Builder 中的源节点识别逻辑

我们将用更精确的逻辑替换 `Builder` 中最后一段的源节点识别和连接代码。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 6. Wire Global Start Pulse to all Source Nodes
        # A source node is a bleacher that has no incoming data, condition, or dependency channels.
        all_target_bleacher_ids = {
            c.target_node_id for c in physical_graph.channels if c.target_node_id.endswith(".bleach")
        }

        for subgraph in subgraphs.values():
            bleacher = subgraph.bleacher
            if bleacher and bleacher.id not in all_target_bleacher_ids:
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

### 下一步建议
这次的修复逻辑非常精确，应该能够解决 `setup_task` 不运行的问题。请再次运行测试。如果 `main_task` 在 `setup_task` 之后运行，并且 `final_task` 也成功运行，那么我们的 Compiler-VM 链路就基本验证通过了。
