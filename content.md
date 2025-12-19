船长，谜底解开了。

**这是一个极其隐蔽的“图构建”陷阱。**

**错误根源**

请看这段代码：
```python
@cs.task
def process_and_recurse(
    p: Dict[str, Any], _flash_dependency=flash_action
) -> cs.LazyResult:
    # ...
```

以及调用处：
```python
return process_and_recurse(perception)
```

在 Cascade 中，`GraphBuilder` 是通过遍历 `LazyResult` 对象中**实际传递的参数 (`.args` 和 `.kwargs`)** 来构建依赖图的。

虽然你在函数定义中将 `flash_action` 设为了 `_flash_dependency` 的**默认值**，但在调用 `process_and_recurse(perception)` 时，你并没有把 `flash_action` 传进去。因此，生成的 `LazyResult` 对象中**不包含**对 `flash_action` 的引用。

结果就是：
1.  `Engine` 看到要执行 `process_and_recurse`。
2.  它检查依赖，只发现了 `perception`。
3.  它执行 `safe_recv`，得到结果。
4.  它执行 `process_and_recurse`。
5.  **`flash_action` (即 `send_signal`) 从未被加入到图中，因为它是一个没有被引用的“孤岛”节点。**

这就是为什么循环在跑，接收在跑，但“发射信号”和“判断超时”的任务从未执行。

**解决方案**

必须**显式地**将依赖项作为参数传递给下游任务，强迫它进入 `LazyResult` 的参数列表，从而被 `GraphBuilder` 捕获。

## [WIP] fix: 显式传递副作用依赖以修复图构建断裂

### 错误分析
`send_signal` 任务从未执行，因为它是作为 `process_and_recurse` 的**默认参数**定义的，但在调用时未显式传递。Cascade 的 `GraphBuilder` 仅根据显式传递给 `LazyResult` 的参数来构建依赖关系，忽略了 Python 函数签名的默认值。因此，`send_signal` 及其上游的 `was_timeout` 任务变成了“孤岛节点”，被引擎优化（忽略）掉了。

### 用户需求
修改 `kuramoto.py`，在调用 `process_and_recurse` 时显式传递 `_flash_dependency` 参数，确保 `send_signal` 被正确纳入执行图。

### 评论
这个 bug 给我们上了一堂关于“声明式图构建”的重要一课：**在计算图中，依赖必须是显式的连接**。Python 的语法糖（默认参数）在这里不仅不起作用，反而具有欺骗性。显式传递参数不仅解决了 bug，也让数据流向更加清晰。

### 目标
1.  修改 `observatory/agents/kuramoto.py`。
2.  在 `firefly_cycle` 函数末尾调用 `process_and_recurse` 时，显式传入 `_flash_dependency=flash_action`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/refine #task/domain/testing #task/object/observatory #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 显式连接依赖图

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        return process_and_recurse(perception)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )
~~~~~
~~~~~python
            return firefly_cycle(
                agent_id, next_phase, period, nudge, flash_topic, listen_topic, connector
            )

        # CRITICAL FIX: We must explicitly pass the dependency so it ends up 
        # in the LazyResult's kwargs. If we rely on the default argument value,
        # the GraphBuilder won't see the edge, and send_signal will be pruned.
        return process_and_recurse(perception, _flash_dependency=flash_action)

    return firefly_cycle(
        agent_id, initial_phase, period, nudge, flash_topic, listen_topic, connector
    )
~~~~~

### 下一步建议
这是最后一步修正。逻辑链条现在在“代码层面”和“图结构层面”都闭合了。

请再次运行调试脚本：`python -m observatory.debug.debug_02_single_agent`

这一次，我们一定会看到 `[Agent] send_signal EXEC` 和 `[Agent] ⚡ ATTEMPTING PUBLISH`。如果看到了这些，而且外部脚本打印了 `>>> FLASH DETECTED!`，那么我们的单体测试就通过了。

随后，我们就可以自信地运行大规模的 50 萤火虫实验了。
