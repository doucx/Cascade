## [WIP] fix(compiler): 修复 Validator 发现的端口名称违规

### 错误分析
Validator 继续立功！这次是 `_check_port_connectivity` 捕获到了一个端口名称不匹配的错误：
`GraphValidationError: Channel #14: DataNode 'global.observability.bus' expects input on port 'in', got 'event_token'.`

在 `cascade-compiler/backend/builder.py` 中，我们连接到 `D_life` (DataNode) 时，错误地将目标端口命名为了 `event_token`，而 DataNode 的标准输入端口是 `in`。
`event_token` 应该是 `F_obs` (FuncNode) 的输入端口名，而不是 `D_life` 的。

### 用户需求
修复 `Builder` 中关于观测系统的连线逻辑，确保连接到 `D_life` 的通道使用目标端口 `'in'`。

### 评论
这是一个经典的“复制粘贴”错误。我们把连接到 Observer 的端口名用到了连接到 Bus 的通道上。Validator 成功地在这些错误造成运行时混淆之前拦截了它们。

### 目标
1.  修改 `cascade-compiler/backend/builder.py`。
2.  将所有指向 `d_life_id` 的通道的 `target_port` 从 `event_token` 改为 `in`。

### 基本原理
**DataNode 接口**: 所有 DataNode 默认通过端口 `'in'` 接收 Token，通过端口 `'out'` 输出 Token。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #concept/observability #scope/core #ai/instruct #task/domain/compiler #task/object/builder #task/action/rewire #task/state/end

---

### Script

#### Acts 1: 修复观测系统连线

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="event_token",
                )
            )
~~~~~
~~~~~python.new
            # 3.3 Wire task observability TO the sidecar bus
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.bleacher.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="in",
                )
            )
            physical_graph.channels.append(
                Channel(
                    source_node_id=subgraph.stainer.id,
                    source_port="obs_output",
                    target_node_id=d_life_id,
                    target_port="in",
                )
            )
~~~~~

### 下一步建议
重新运行所有测试。Validator 应该不再报错，且集成测试应该通过。
我们正在逐步清除系统中的熵，使物理场变得纯净、有序且可验证。
