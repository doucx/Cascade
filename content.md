好的，我将遵循 ACA 协议，首先分析《债务监测》文件的时效性，然后对代码库进行新一轮的全面审查，并最终生成一个 Quipu 计划来解决发现的问题。

我已完成分析。

《债务监测》文件中列出的技术债务大部分已经得到解决，但有两项仍然存在。同时，在新一轮代码审查中，我发现了一个与消息传递和测试原则相关的新问题，它暴露了消息总线、本地化文件和集成测试之间的不一致性。

我将生成一个计划，首先更新债务跟踪文件以反映当前状态，然后修复新发现的消息传递层问题。

## [WIP] refactor(messaging): 统一事件契约与消息模板

### 用户需求
1.  分析 `状态检测/债务监测.md` 文件的内容，确定其中列出的技术债务是否已过时。
2.  对整个代码库进行新一轮代码审查，识别新的潜在问题。
3.  根据审查结果，更新债务跟踪文件并修复发现的核心问题。

### 评论
这是一次重要的代码健康度审查。通过确认旧债务的状态并识别新问题，我们可以保持代码库的整洁和可维护性。

本次审查发现的核心问题在于消息传递层：业务逻辑（`Subscriber`）和测试（`test_end_to_end.py`）期望传递结构化数据（如任务列表），但底层消息存储（`MessageStore`）为了兼容一个过时或缺失的消息模板，实现了一个“垫片”或“hack”来将列表转换为字符串。

修复此问题将使系统行为更加一致，移除不必要的代码复杂性，并使我们的测试更真实地反映其“验证意图”的核心原则。

### 目标
1.  **更新债务文件**: 修改 `债务监测.md`，标记已偿还的债务，保留仍然有效的部分。
2.  **创建消息模板**: 创建缺失的 `src/cascade/locales/en/events.json` 文件，使其成为消息格式的唯一事实来源 (Single Source of Truth)。
3.  **移除代码 Hack**: 从 `src/cascade/messaging/bus.py` 中移除将 `target_tasks` 列表转换为字符串的临时逻辑。
4.  **对齐测试**: 更新 `tests/integration/test_end_to_end.py` 中的测试用例，使其断言业务逻辑传递给消息总线的正确数据结构（列表），而不是迁就旧的实现。

### 基本原理
**债务分析结果**:
*   **已偿还**:
    *   **引擎复杂性**: `Engine.run` 已被重构，提取了 `_execute_node_with_policies` 方法。
    *   **事件粒度**: `TaskRetrying` 事件已被实现并在重试循环中正确发布。
    *   **Router/EdgeType 序列化**: `serialize.py` 及其测试已完全支持 `EdgeType` 和 `Router` 对象的序列化与反序列化。
*   **仍然有效**:
    *   **Router 剪枝**: 当前实现仍会执行 `Router` 的所有可能路由分支。
    *   **缓存键健壮性**: 对于包含不可序列化对象的复杂输入，缓存键生成仍然是一个潜在挑战。

**新发现的问题**:
`HumanReadableLogSubscriber` 正确地将 `RunStarted` 事件的 `target_tasks` 列表传递给了 `messaging_bus`。然而，`MessageStore.get` 方法中存在一个特殊的 `if` 判断，它将这个列表手动 `join` 成一个字符串，以适配一个不存在的旧消息模板。

这违反了“验证意图而非实现”的测试原则，因为测试用例被迫断言这个被转换后的数据，而不是业务逻辑的原始意图。

正确的做法是：
1.  在 `events.json` 中定义正确的模板。
2.  移除 `MessageStore` 中的 hack。
3.  让 `CliRenderer` 负责使用模板和数据进行最终渲染。
4.  让测试直接断言传递给 `messaging_bus` 的原始、未修改的数据。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/runtime #comp/tests #concept/state #scope/dx
#ai/instruct
#task/domain/maintenance #task/object/tech-debt #task/action/resolve #task/state/begin

---

### Script

#### Acts 3: 移除 MessageStore 中的临时补丁

现在 `events.json` 成为了格式化的事实来源，我们可以安全地移除 `MessageStore.get` 方法中的特殊处理逻辑。

~~~~~act
patch_file
src/cascade/messaging/bus.py
~~~~~
~~~~~python
    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        # This is a temporary "smart" get to simulate fixing the underlying
        # message template file without actually editing it.
        # It handles the specific case where the run.started event was refactored.
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        if msg_id == "run.started" and "target_tasks" in kwargs:
             # The old template expects {targets}, so we perform the join here
             # This centralizes the logic instead of putting it in the renderer
            kwargs["targets"] = ", ".join(kwargs["target_tasks"])
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"
~~~~~
~~~~~python
    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"
~~~~~

#### Acts 4: 更新集成测试以验证正确的意图

最后，修改 `test_end_to_end.py` 中的测试，使其直接断言 `messaging_bus` 接收到了 `target_tasks` 列表，这才是 `Subscriber` 的真正意图。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
    # Assertions are now on the INTENT (semantic ID), not the output!
    # Find the specific call to 'run.started' to make the test more robust
    run_started_call = next(
        c for c in mock_messaging_bus.info.call_args_list if c.args[0] == 'run.started'
    )
    
    # Assert that the new, structured keyword is used
    assert "target_tasks" in run_started_call.kwargs
    assert "greet" in run_started_call.kwargs["target_tasks"] # Check for list membership
    
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
~~~~~
~~~~~python
    # Assertions are now on the INTENT (semantic ID), not the output!
    # The subscriber should pass the list of target tasks directly.
    mock_messaging_bus.info.assert_any_call(
        "run.started", target_tasks=["greet"]
    )
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
~~~~~

### 下一步建议
我们已经完成了本次代码健康度审查和修复。下一步，我建议我们解决《债务监测》中遗留的、优先级较高的问题：**Router 未选择分支的剪枝**。实现这个功能将显著提升包含 `cs.Router` 的工作流的执行效率，避免不必要的计算开销。
