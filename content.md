# [WIP] fix: 在 ArgumentResolver 的 Fast Path 中同样应用 Jump Override 优先级

## 摘要头
## [WIP] fix(engine): 修复 Fast Path 中 TCO 跳转参数被覆盖的问题

### 错误分析
之前的修复只覆盖了 `ArgumentResolver` 的“复杂路径 (Complex Path)”，但 `ArgumentResolver` 包含一个针对简单任务的“快速路径 (Fast Path)”。
1.  **现状**：我的测试用例 `recursive_task` 是一个简单的任务（没有 Inject，没有复杂结构），因此运行时走了 `Fast Path`。
2.  **遗漏**：在 `Fast Path` 的逻辑中，依然存在“先应用 Bindings（含 Overrides），再无条件解析 Edges 并覆盖”的错误顺序。
3.  **结果**：即使 Override 存在，Edge 依然被解析并覆盖了 Override 的值，导致测试依然失败。

### 用户需求
确保无论任务走的是 Fast Path 还是 Complex Path，`cs.Jump` 提供的参数覆盖都必须优于静态图的依赖。

### 评论
这是一个典型的“优化导致的分叉”问题。由于有两个代码路径处理相似的逻辑，修复必须同时应用到两处。

### 目标
在 `ArgumentResolver` 的 `Fast Path` 处理循环中，加入与 `Complex Path` 相同的 Override 检查逻辑。

### 基本原理
在 `Fast Path` 的 `incoming_edges` 循环中，如果 `edge.arg_name` 存在于 `input_overrides` 中，则跳过该 Edge 的解析和赋值。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/tco #scope/core #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 ArgumentResolver 的 Fast Path

我们将对 `resolvers.py` 进行补丁，这次针对 `FAST PATH` 部分。同时我也会检查一下之前对 `Complex Path` 的修改是否需要调整（不需要，之前的修改是正确的，只是不完整）。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
            f_kwargs = {k: v for k, v in bindings.items() if not k.isdigit()}

            # 2. Fill from edges
            for edge in incoming_edges:
                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = val
                else:
                    f_kwargs[edge.arg_name] = val

            return f_args, f_kwargs
~~~~~
~~~~~python
            f_kwargs = {k: v for k, v in bindings.items() if not k.isdigit()}

            # 2. Fill from edges
            for edge in incoming_edges:
                # [CRITICAL FIX] Fast Path Priority Check:
                # See Complex Path below for reasoning. Overrides from Jump must take precedence.
                if input_overrides and edge.arg_name in input_overrides:
                    continue

                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(f_args) <= idx:
                        f_args.append(None)
                    f_args[idx] = val
                else:
                    f_kwargs[edge.arg_name] = val

            return f_args, f_kwargs
~~~~~

### 下一步建议
再次运行测试 `pytest tests/engine/e2e/test_tco_param_override.py`。这次应该能覆盖所有路径。
