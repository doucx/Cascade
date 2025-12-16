分析表明，在 `Engine._execute_graph` 的异常处理逻辑中（特别是当目标任务未执行时），代码试图从 `plan` 中查找目标节点以获取其名称。然而，`plan` 现在是分层的 `List[List[Node]]`，直接迭代它得到的 `n` 是一个列表（stage），而不是 `Node`，因此引发了 `AttributeError: 'list' object has no attribute 'id'`。

## [WIP] fix(runtime): Resolve plan traversal issue in error handling

### 用户需求
修复在 `Engine` 异常处理逻辑中遍历分层 `plan` 导致的 `AttributeError`。这阻止了在任务跳过场景下正确抛出 `DependencyMissingError`。

### 评论
这是分层执行计划重构的遗留问题。在查找特定节点时，必须先将分层计划扁平化。

### 目标
修改 `src/cascade/runtime/engine.py` 中用于生成错误消息的节点查找逻辑，使其正确遍历嵌套的 `ExecutionPlan`。

### 基本原理
在 `_execute_graph` 方法的末尾，当需要从 `plan` 中找到 `target_node` 时，代码当前是 `next(n for n in plan if n.id == target._uuid)`。我们将使用 `itertools.chain` 或列表推导式将 `plan` 扁平化后再进行搜索。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/tests
#ai/instruct
#task/domain/runtime #task/object/error-handling #task/action/fix
#task/state/continue

---

### Script

#### Acts 1: 修复 Engine 中的节点查找逻辑

修改 `src/cascade/runtime/engine.py`，修正错误处理块中的节点查找代码。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
            if target._uuid in skipped_node_ids:
                # We need to find the node name for the error message
                target_node = next(n for n in plan if n.id == target._uuid)

                # The "dependency" here is the task itself, because it was skipped.
                raise DependencyMissingError(
~~~~~
~~~~~python
            if target._uuid in skipped_node_ids:
                # We need to find the node name for the error message
                # Flatten plan to search for the node
                all_nodes = (node for stage in plan for node in stage)
                target_node = next(n for n in all_nodes if n.id == target._uuid)

                # The "dependency" here is the task itself, because it was skipped.
                raise DependencyMissingError(
~~~~~

### 下一步建议
这次修复针对性很强。修复后，所有测试应该通过。我们可以进行提交。
