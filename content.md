好的，执行战术修复。

我将生成一个计划，直接修正 `VMExecutionStrategy` 中对 `ChannelDef` 对象的错误方法调用，使其与静态数据模型的定义保持一致。

## [WIP] fix(engine): 修正 VMExecutionStrategy 中对静态 ChannelDef 的访问方式

### 错误分析
在 `VMExecutionStrategy` 中，代码尝试对 `cascade.spec.topology.ChannelDef` 对象调用 `.match()` 方法。这是一个概念性错误，因为 `match()` 方法定义在 `cascade.vm.reactor.model.Channel`（动态物理对象）上，而 `ChannelDef` 仅仅是一个静态的数据传输对象（DTO），它包含一个名为 `tag_filter` 的字符串字段。正确的做法是直接比较该字段的值。

### 用户需求
修复 `AttributeError: 'ChannelDef' object has no attribute 'match'` 错误，使 `VMExecutionStrategy` 能够正确识别 TCO 测试中的输出通道。

### 评论
这是一个典型的静态/动态模型混淆错误。通过将方法调用改为直接的属性比较，我们能快速打通测试，验证 `Reactor` 和 `Compiler` 在 TCO 场景下的核心集成逻辑是否正确。

### 目标
1.  定位到 `packages/cascade-engine/src/cascade/runtime/strategies/vm.py` 文件中的错误行。
2.  将 `c.match("default")` 替换为 `c.tag_filter == "default"`。

### 基本原理
`BipartiteGraph` 及其包含的 `ChannelDef` 是由编译器生成的静态蓝图。在分析这个蓝图时，我们应该直接访问其数据字段，而不是期望它拥有动态行为。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正对 ChannelDef 的属性访问

我们将修改 `vm.py`，确保对 `ChannelDef` 的访问符合其数据类定义。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
            result_channel_def = next((
                c for c in topology.channels 
                if c.source_node_instance_hash == root_func_hash 
                and c.port_name == "result" 
                and c.match("default")
            ), None)
~~~~~
~~~~~python.new
            result_channel_def = next((
                c for c in topology.channels
                if c.source_node_instance_hash == root_func_hash
                and c.port_name == "result"
                and c.tag_filter == "default"
            ), None)
~~~~~

### 下一步建议
现在我们已经修复了阻塞性的 `AttributeError`。请重新运行测试，特别是 `test_vm_strategy_tco.py`。这次，`VMExecutionStrategy` 应该能够完整地执行，我们将会看到 TCO 逻辑在新的 Reactor 架构下的真实表现。
