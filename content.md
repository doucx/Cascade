分析正确。测试失败了，这是我的疏忽。

测试失败的根本原因在于 `standard_stainer` 的实现。它在为 `TaskExecutionFinished` 事件创建 `EventIR` 时，为了生成 `result_preview`，无条件地将任务的返回结果（`result_payload`）转换为了字符串：

`"result_preview": str(result_payload)[:100]`

在我们的新异步模型中，`worker` (即 `source_task`) 的结果被 `LocalComputeService` 存入 `ObjectStore`，返回的是一个 `Ref` 对象。因此，当 `Stainer` 接收到这个结果时，`result_payload` 就是一个 `Ref` 实例。`str(Ref(...))` 会产生一个类似 `"Ref(uri='...')"` 的字符串。

这个字符串随后被放入事件的 `result_preview` 字段。测试代码接收到这个事件，并尝试将这个**字符串**传递给 `runner.object_store.get()`，而该方法期望接收一个真正的 `Ref` **对象**，因此在尝试访问 `.uri` 属性时抛出了 `AttributeError: 'str' object has no attribute 'uri'`。

我们将修复 `standard_stainer` 的逻辑。它应该足够智能，能够区分 `Ref` 对象和其他可字符串化的结果。如果结果是一个 `Ref` 对象，它应该直接将该对象放入 `result_preview`，而不是其字符串表示。

这将确保事件携带的是高保真的、可直接使用的引用对象，从而修复测试并使我们的可观测性系统更加健壮。

我将生成一个计划来应用此修复。

## [WIP] fix(std): 防止 stainer 在事件预览中字符串化 Ref 对象

### 用户需求

修复 `standard_stainer` 的实现，使其在处理 `Ref` 类型的任务结果时，不要将其转换为字符串，而是直接将 `Ref` 对象本身放入事件的 `result_preview` 字段。

### 评论

这是一个关键的修复，它暴露了在数据流中保持类型保真度的重要性。通过确保 `Ref` 对象在整个可观测性管道中保持其对象身份，我们不仅修复了当前的测试失败，还增强了事件系统的整体能力，使其能够传递更丰富、更具功能性的数据，而不仅仅是文本表示。

### 目标

1.  定位 `packages/cascade-std/src/cascade/std/triad/stainer.py` 中 `result_preview` 的生成逻辑。
2.  修改该逻辑，增加一个类型检查：如果 `result_payload` 是一个 `Ref` 实例，则直接使用它；否则，才进行字符串转换和截断。
3.  确保修复后的代码能够正确处理两种类型的结果。

### 基本原理

通过在 `standard_stainer` 中引入一个简单的 `isinstance(result_payload, Ref)` 判断，我们可以优雅地处理不同类型的数据。这是一种简单、直接且影响范围最小的修复方式，它直接解决了问题的根源，即 `Ref` 对象被过早地、不恰当地序列化为字符串。

### 标签

#intent/fix #flow/ready #priority/high #comp/std #comp/vm #concept/executor #scope/core #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 修复 `standard_stainer`

我们将修改 `stainer.py`，为其添加处理 `Ref` 对象的逻辑。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": task_name,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": str(result_payload)[:100]
            if state == EventState.SUCCEEDED
            else None,
        },
    }
~~~~~
~~~~~python.new
    # Handle preview generation: pass Refs through, stringify others.
    preview = None
    if state == EventState.SUCCEEDED:
        from cascade.spec.physical.object import Ref

        if isinstance(result_payload, Ref):
            preview = result_payload
        else:
            preview = str(result_payload)[:100]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": task_name,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": preview,
        },
    }
~~~~~

### 下一步建议

我们已经应用了修复程序。现在，我们应该重新运行 `test_source_node_execution.py` 测试。如果一切顺利，它现在应该会通过，这将确认我们的整个异步执行和可观测性流程已经成功集成。
