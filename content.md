## [WIP] fix(runtime): Ignore control edges in LocalExecutor

### 错误分析
测试 `test_run_if_true` 失败，报错 `TypeError: ... got an unexpected keyword argument '_condition'`。

**原因**:
1.  我们通过在图中添加 `arg_name="_condition"` 的边来表示条件依赖。
2.  `LocalExecutor` 在准备任务参数时，遍历了所有指向该节点的边，并将 `arg_name` 用作关键字参数传给函数。
3.  它错误地将 `_condition` 也当作普通参数传递给了目标函数，而目标函数并不接受该参数。

**解决方案**:
修改 `LocalExecutor`，在参数组装阶段显式忽略 `arg_name` 为 `_condition` 的边。这些边仅用于 `Engine` 层的调度逻辑，不应参与函数调用。

### 用户需求
修复条件工作流实现中的参数传递错误，确保测试通过。

### 评论
这是一个经典的“泄漏抽象”问题。底层的图结构（Edge）承载了多种语义（数据流 vs 控制流），执行器需要能区分它们。

### 目标
1.  修改 `src/cascade/adapters/executors/local.py`，过滤掉控制流边。
2.  确保 `tests/test_control_flow.py` 通过。

### 基本原理
在 `LocalExecutor` 的循环中添加简单的 `if edge.arg_name == "_condition": continue` 检查。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/control-flow #scope/core #ai/instruct #task/domain/core #task/object/local-executor #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 LocalExecutor

修改参数组装逻辑，忽略 `_condition` 边。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        sorted_indices = sorted(positional_args.keys())
~~~~~
~~~~~python
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            # Skip control flow edges
            if edge.arg_name == "_condition":
                continue

            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        sorted_indices = sorted(positional_args.keys())
~~~~~

### 下一步建议
修复后，所有测试应该通过。通过后，我将提交包含条件工作流功能的代码。
