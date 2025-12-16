很好，我们成功解决了循环导入问题（所有模块现在都能被收集，74个测试通过），但是核心的错误处理逻辑仍然存在一个**尾部 bug**。

### 核心问题分析：Engine 的终结逻辑错误

在 `tests/runtime/test_control_flow.py` 的两个失败用例中，我们观察到：

1.  `test_run_if_false`: `action()` 任务被 `_should_skip` 标记为跳过 (`ConditionFalse`)。
2.  `test_cascade_skip`: `step_a()` 被跳过 (`ConditionFalse`)，随后 `step_b()` 被跳过 (`UpstreamSkipped`)。

在上述两种情况下，`target` 任务本身或其所有依赖都被跳过了。

**Engine 逻辑 (`src/cascade/runtime/engine.py:277`)**:
```python
        # ... 循环结束
        return results[target._uuid]
E       KeyError: '...'
```
如果 `target` 任务被跳过，它的结果就不会存在于 `results` 字典中。这导致 `Engine` 最终以一个普通的 `KeyError` 退出，而不是我们期望的 `DependencyMissingError`。

**为什么它没有触发 `DependencyMissingError`?**

`DependencyMissingError` 应该在 **下游任务尝试获取上游被跳过结果** 时触发。

在 `test_run_if_false` 中：
- 拓扑顺序是 `condition -> action`。
- `condition` 运行并返回 `False`。
- `action` 运行到 `_should_skip` 时被跳过。
- 循环结束，`Engine` 试图返回 `action` 的结果，但 `action` 被跳过，`results` 中没有它的 ID，因此抛出 `KeyError`。

**修正方案**:

当 `Engine` 试图返回 `target` 结果时，如果 `target` 节点 ID 不在 `results` 中，说明目标任务本身或其所有依赖都被跳过了。此时，我们应该检查跳过的原因，并抛出一个更具语义的异常，而不是依赖底层的 `KeyError`。

我们将修改 `_execute_graph` 的返回逻辑。

## [WIP] fix(engine): 修复目标任务被跳过时抛出 KeyError 的问题

### 目标
1.  修改 `Engine._execute_graph` 的返回逻辑，检查 `target._uuid` 是否在 `results` 中。
2.  如果缺失，则检查 `target` 节点是否在 `skipped_node_ids` 集合中。
3.  如果是，则抛出语义正确的 `DependencyMissingError`，指出目标任务缺失。
4.  如果否，则说明发生了未知的内部错误（应该保留 `KeyError` 或抛出内部异常）。

### 基本原理
确保即使是工作流的终点节点被控制流逻辑跳过时，也能提供清晰的诊断信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/control-flow #scope/core #ai/instruct #task/domain/runtime #task/object/exception-handling #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 修复 `src/cascade/runtime/engine.py` 的返回逻辑

修改 `_execute_graph` 的最后几行。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        for node in plan:
            if node.node_type == "param":
                continue

            skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
            if skip_reason:
                skipped_node_ids.add(node.id)
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason=skip_reason,
                    )
                )
                continue

            # Execute Node
            results[node.id] = await self._execute_node_with_policies(
                node, graph, results, active_resources, run_id, params
            )

        return results[target._uuid]
~~~~~
~~~~~python
        for node in plan:
            if node.node_type == "param":
                continue

            skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
            if skip_reason:
                skipped_node_ids.add(node.id)
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason=skip_reason,
                    )
                )
                continue

            # Execute Node
            results[node.id] = await self._execute_node_with_policies(
                node, graph, results, active_resources, run_id, params
            )
        
        # Final check: Was the target task executed?
        if target._uuid not in results:
            # If target was skipped itself, or skipped because of upstream.
            if target._uuid in skipped_node_ids:
                # We need to find the node name for the error message
                target_node = next(n for n in plan if n.id == target._uuid)
                
                # The "dependency" here is the task itself, because it was skipped.
                raise DependencyMissingError(
                    task_id=target_node.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped."
                )
            
            # If target is missing for unknown reasons, re-raise original KeyError
            raise KeyError(target._uuid)

        return results[target._uuid]
~~~~~

### 下一步建议
我们已经修复了 `Engine` 的最终返回逻辑，使其在目标任务被跳过时抛出正确的异常。请指示执行测试。
