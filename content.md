简要回答
我们之前的重构虽然方向正确，但遗漏了一个关键的运行时拦截器：`GraphExecutionStrategy` 中遗留了显式跳过 `ParamNode` 的代码。这导致 `ParamNode` 永远不会被调度执行，从而不产生结果，引发下游的 `DependencyMissingError`。

## [WIP] fix(runtime): 移除 GraphStrategy 对 ParamNode 的执行拦截

### 错误分析
测试失败 `DependencyMissingError: ... Dependency ... did not produce a result` 的根本原因是 `ParamNode` 没有产生结果。
经过代码审查，在 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py` 的 `_execute_graph` 方法中发现如下逻辑：
```python
                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # <---【罪魁祸首】
```
这一逻辑是旧架构的遗留物（当时 `ParamNode` 由 `ArgumentResolver` 的特殊分支隐式处理）。既然我们已经将 `ParamNode` 重构为标准的、带有 `_callable` 的 `TaskNode` 子类，并希望它走标准执行流程，就必须删除这个拦截检查。

### 用户需求
1.  移除 `GraphExecutionStrategy` 中对 `"param"` 类型节点的跳过逻辑。
2.  确保 `ParamNode` 能够被 `Processor` 正常调度和执行。

### 评论
这是一个典型的“影子逻辑”问题。当我们进行架构迁移时，必须清理所有旧路径的痕迹。删除这两行代码将打通 `ParamNode` 新的执行生命周期。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py`，删除 `if node.node_type == "param": continue`。

### 基本原理
通过允许 `ParamNode` 进入执行循环，`Engine` 将会调用 `Processor.process(ParamNode)`。这将触发我们之前更新的 `ArgumentResolver` 逻辑（注入 `params_context`），然后由 `Executor` 执行 `_get_param_value`，最终将参数值存入 `StateBackend`，满足下游依赖。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/runtime #concept/execution-strategy #ai/instruct #task/domain/core #task/object/param-node #task/action/enable-execution #task/state/continue

---

### Script

#### Acts 1: 启用 ParamNode 执行
移除 `GraphExecutionStrategy` 中的类型拦截，允许 `ParamNode` 像不同任务一样被调度。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    # ASYNC CHECK
                    skip_reason = await flow_manager.should_skip(node, state_backend)
~~~~~
~~~~~python.new
                for node in pending_nodes_in_stage:
                    # ASYNC CHECK
                    skip_reason = await flow_manager.should_skip(node, state_backend)
~~~~~

### 下一步建议
这应该是修复 `DependencyMissingError` 的最后一块拼图。建议重新运行所有相关测试：
1. `tests/e2e/runtime/test_tco_param_override.py`
2. `packages/cascade-engine/tests/runtime/test_input_execution.py`
3. `packages/cascade-spec/tests/spec/test_routing.py`
