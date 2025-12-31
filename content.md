简要回答：
分析测试失败原因：
1.  **`test_reactor_propagation` 失败**: 测试仅调用了 `register_node`，但 `Reactor` 的路由逻辑依赖于 `Channel`。当前的 `Reactor` 实现不会自动从 `FuncNode` 的物理连接（Port）推导 `Channel`，导致 `ExecutionFinished` 事件处理时找不到路由路径，数据流中断。
2.  **`test_reactor_event_driven_potential_update` 失败**: 表现为 `DataNode` 未被更新。这虽然奇怪，但鉴于上述发现，极有可能是因为我对 `Reactor` 的“物理感知”能力期望过高。

解决方案：
增强 `Reactor.register_node` 方法。当注册一个 `FuncNode` 时，它应该遍历该节点的 `outputs` 端口。对于每一个连接了 `DataNode` 的输出端口，自动创建一个默认的 `Channel`（Tag="default"）并注册。这样就实现了物理拓扑到路由表的自动映射。

## [WIP] fix: Enhance Reactor topology discovery

### 用户需求
修复 `Reactor` 测试失败的问题。

### 评论
当前的 `Reactor` 被动地等待 `register_channel`，这使得测试（以及未来的编译器）必须繁琐地手动声明每一个连接。通过让 `Reactor` 自动发现 `FuncNode` 的物理连接，我们不仅修复了测试，还简化了 API。

### 目标
修改 `packages/cascade-vm/src/cascade/vm/reactor/core.py` 中的 `register_node` 方法。

### 基本原理
物理层 (`FuncNode` + `Port` + `DataNode`) 已经定义了静态拓扑。`Reactor` 作为物理引擎，应该在加载物理节点时自动建立默认的“光路”（Channel）。只有当需要非默认路由（如特殊 Tag）时，才需要显式定义 Channel。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/topology #scope/core #ai/refine #task/domain/runtime #task/object/reactor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 `Reactor.register_node` 以支持自动拓扑发现

我们将修改 `core.py`，导入 `Channel` 类（如果尚未导入），并在 `register_node` 中添加自动发现逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes
        if isinstance(node, FuncNode):
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)

    def register_channel(self, channel: Channel):
~~~~~
~~~~~python.new
    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes and Auto-discover Channels
        if isinstance(node, FuncNode):
            # 1. Reverse dependency map (DataNode -> Downstream FuncNodes)
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)
            
            # 2. Auto-discover Output Channels (Physics -> Routing)
            # If a port is connected to a DataNode physically, implies a default channel.
            for port_name, port in node.outputs.items():
                if port.target:
                    # Check if a channel already exists for this path to avoid duplicates
                    # or overriding explicit custom channels.
                    existing = any(
                        c.output_name == port_name and c.match("default")
                        for c in self._channels_by_source.get(node.name, [])
                    )
                    if not existing:
                        # Create implicit default channel
                        default_channel = Channel(
                            source=node,
                            target=port.target,
                            output_name=port_name,
                            tag_filter="default"
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
~~~~~

### 下一步建议
运行测试。如果 `test_reactor_propagation` 通过了，说明路由逻辑修复了。如果 `test_reactor_event_driven_potential_update` 依然失败，我们需要进一步排查 `DataNode` 的状态更新问题。鉴于该测试只依赖 `DataNode` 和事件处理（不涉及路由），如果它还挂，可能是更基础的引用或异步问题。
