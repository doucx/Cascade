# [WIP] fix: 修复 TCO 跳转参数无法覆盖 Param 依赖的问题

## 摘要头
## [WIP] fix(engine): 确立 Jump Override 在参数解析中的最高优先级

### 错误分析
当前 `ArgumentResolver` 的解析逻辑存在优先级倒置问题：
1.  **现状**：先应用 `Bindings`（包含 `input_overrides`），然后解析 `Edges`（上游依赖）。如果存在 Edge，它会无条件覆盖 Binding 中的值。
2.  **冲突**：当使用 `cs.Param` 时，目标参数上存在一条来自 `_get_param_value` 的 DATA Edge。
3.  **后果**：即使 `cs.Jump` 传递了新的 `data`（作为 `input_overrides`），解析器在第二步遍历 Edges 时，依然会重新从 `_get_param_value` 拉取原始值（例如 10），覆盖了 Jump 传递的递减值（例如 9）。导致递归状态无法更新，陷入死循环。

### 用户需求
用户希望在使用 `cs.Param` 作为初始值的递归任务中，`cs.Jump` 传递的参数能够正确生效，实现正常的递归递减，而不是死循环。

### 评论
这是一个涉及核心运行时正确性的关键修复。TCO（尾调用优化）机制依赖于“本次 Jump 的输出覆盖下一次的输入”。如果这个覆盖机制被静态图的依赖关系否定了，TCO 对于这就无法用于任何非字面量输入的场景。

### 目标
修改 `ArgumentResolver` 的逻辑，确保 `input_overrides`（代表运行时的动态干预）具有比静态图 Edge 更高的优先级。

### 基本原理
在 `ArgumentResolver._resolve_internal` 遍历 `incoming_edges` 时，增加一个检查：如果某个参数名已经在 `input_overrides` 中被显式定义，则**跳过**对该参数对应的 Edge 的解析。这在语义上是正确的：Jump 意图明确表示“忽略旧的输入来源，使用我提供的新值”。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/tco #scope/core #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 创建复现测试用例
我们将创建一个端到端测试，模拟用户报告的 `cs.Param` + `cs.Jump` 场景，并增加防死循环机制。

~~~~~act
write_file
tests/engine/e2e/test_tco_param_override.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.common.messaging import MessageBus

@pytest.mark.asyncio
async def test_jump_overrides_param():
    """
    Test that data provided by cs.Jump (input_overrides) takes precedence over
    upstream dependencies (like cs.Param) defined in the static graph.
    """
    results = []

    @cs.task
    def recursive_task(n):
        # Safety break to prevent infinite loop if bug exists
        if len(results) > 10:
            return "InfiniteLoopDetected"
            
        results.append(n)
        if n <= 0:
            return "Done"
        
        # Pass n-1 to the next iteration
        return cs.Jump(target_key="continue", data=n - 1)

    # Define workflow: Initial input comes from a Param (Edge dependency)
    # If the bug exists, the Jump data (n-1) will be ignored, and Param (3) will be used every time.
    t = recursive_task(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    
    # Run with initial param n=3
    final_res = await engine.run(t, params={"n": 3})

    # Expect: [3, 2, 1, 0]
    # If bug: [3, 3, 3, ...] -> "InfiniteLoopDetected"
    assert results == [3, 2, 1, 0]
    assert final_res == "Done"
~~~~~

#### Acts 2: 修复 ArgumentResolver
修改 `resolvers.py`，在解析 Edge 前检查 override 状态。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
        # 2. Overlay Dependencies from Edges
        # [OPTIMIZATION] Filter edges once using list comprehension
        incoming_edges = [
            e
            for e in graph.edges
            if e.target.structural_id == node.structural_id
            and e.edge_type == EdgeType.DATA
        ]

        if incoming_edges:
            for edge in incoming_edges:
                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )

                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    kwargs[edge.arg_name] = val
~~~~~
~~~~~python
        # 2. Overlay Dependencies from Edges
        # [OPTIMIZATION] Filter edges once using list comprehension
        incoming_edges = [
            e
            for e in graph.edges
            if e.target.structural_id == node.structural_id
            and e.edge_type == EdgeType.DATA
        ]

        if incoming_edges:
            for edge in incoming_edges:
                # [CRITICAL FIX] Priority Check:
                # If this argument is already provided by an override (e.g., from a TCO Jump),
                # do NOT overwrite it with the upstream dependency. The override represents
                # the latest state of the loop and must take precedence over the static graph structure.
                if input_overrides and edge.arg_name in input_overrides:
                    continue

                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )

                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    kwargs[edge.arg_name] = val
~~~~~

### 下一步建议
执行测试 `pytest tests/engine/e2e/test_tco_param_override.py` 以验证修复。如果通过，这标志着 Cascade 的递归能力达到了一个新的健壮性水平，能够支持更复杂的动态输入场景。
