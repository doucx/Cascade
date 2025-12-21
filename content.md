好的，我将修复 `engine.py` 中 `flow_manager` 的作用域问题。

## [WIP] fix: 修复 Engine 中的变量作用域错误

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 修复 `engine.py` 中的变量引用

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
~~~~~
~~~~~python
                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if self.flow_manager:
                            self.flow_manager.register_result(
                                node.id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass
~~~~~
~~~~~python
                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(
                                node.id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass
~~~~~

### 下一步建议
现在 `engine.py` 应该已经彻底修复了。请再次运行 `observatory/benchmarks/tco_performance.py`，我们期待看到真正的性能飞跃。

```bash
python observatory/benchmarks/tco_performance.py
```
