分析表明，大量的 `AttributeError` 失败是因为 `Engine` 和工具代码仍然假设 `Solver` 返回的是扁平的节点列表，而实际上它现在返回的是分层的列表（`List[List[Node]]`）。我们需要更新这些消费端以适配新的数据结构。

## [WIP] fix(runtime): Adapt consumers to staged execution plan

### 用户需求
修复因引入分层执行计划（Staged Execution Plan）而导致的大量单元测试失败。`Engine`、`dry_run` 工具和相关测试用例需要更新，以正确处理嵌套的列表结构。

### 评论
这是重构过程中的必要清理工作。引入新的数据结构（分层计划）破坏了现有的假设，我们需要恢复这些组件的兼容性。

### 目标
1.  修改 `src/cascade/runtime/engine.py` 中的 `_scan_for_resources` 方法，使其能够处理嵌套的 `ExecutionPlan`。
2.  修改 `src/cascade/tools/preview.py` 中的 `_analyze_plan`，使其能够正确计算总步数并遍历分层计划。
3.  修改 `tests/adapters/solvers/test_native.py`，更新针对 `NativeSolver` 输出结构的断言。

### 基本原理
*   **Engine**: `_scan_for_resources` 需要遍历所有节点。对于分层计划，这意味着需要两层循环（遍历 Stage -> 遍历 Node）或先将其扁平化。我们将采用扁平化处理，因为资源扫描不关心执行顺序。
*   **Preview Tool**: `dry_run` 的显示逻辑需要展平结构，以便按顺序打印每个节点。
*   **Tests**: 测试断言必须反映新的、更优化的执行顺序（即并行任务在同一层）。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/tools #comp/tests
#ai/instruct
#task/domain/runtime #task/object/execution-plan #task/action/fix
#task/state/continue

---

### Script

#### Acts 1: 修复 Engine 的资源扫描

修改 `src/cascade/runtime/engine.py`，更新 `_scan_for_resources` 以处理分层计划。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        required = set()
        for node in plan:
            # Check literal inputs
            for value in node.literal_inputs.values():
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: List[List[Node]]) -> set[str]:
        required = set()
        # Flatten the staged plan for scanning
        all_nodes = [node for stage in plan for node in stage]
        for node in all_nodes:
            # Check literal inputs
            for value in node.literal_inputs.values():
~~~~~

#### Acts 2: 修复 Preview 工具

修改 `src/cascade/tools/preview.py`，使其能正确迭代分层计划。

~~~~~act
patch_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    total_steps = len(plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    for i, node in enumerate(plan, 1):
        bus.publish(
            PlanNodeInspected(
                run_id=target._uuid,
                index=i,
                total_nodes=total_steps,
                node_id=node.id,
                node_name=node.name,
                literal_inputs=node.literal_inputs,
            )
        )

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))
~~~~~
~~~~~python
    # 2. Resolve the execution plan (topological sort)
    plan = engine.solver.resolve(graph)
    # Calculate total nodes across all stages
    total_steps = sum(len(stage) for stage in plan)

    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    current_index = 1
    for stage in plan:
        for node in stage:
            bus.publish(
                PlanNodeInspected(
                    run_id=target._uuid,
                    index=current_index,
                    total_nodes=total_steps,
                    node_id=node.id,
                    node_name=node.name,
                    literal_inputs=node.literal_inputs,
                )
            )
            current_index += 1

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))
~~~~~

#### Acts 3: 更新 Solver 测试

修改 `tests/adapters/solvers/test_native.py`，以匹配新的分层输出。

~~~~~act
patch_file
tests/adapters/solvers/test_native.py
~~~~~
~~~~~python
    graph = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)

    assert len(plan) == 4

    # Node A must be first
    assert plan[0].name == "t_a"
    # Node D must be last
    assert plan[-1].name == "t_d"

    # Nodes B and C can be in any order in between
    middle_names = {plan[1].name, plan[2].name}
    assert middle_names == {"t_b", "t_c"}
~~~~~
~~~~~python
    graph = build_graph(r_d)
    solver = NativeSolver()
    plan = solver.resolve(graph)

    # Should have 3 stages: [A], [B, C], [D]
    assert len(plan) == 3

    # Stage 0: A
    assert len(plan[0]) == 1
    assert plan[0][0].name == "t_a"
    
    # Stage 1: B and C (Parallel)
    assert len(plan[1]) == 2
    middle_names = {n.name for n in plan[1]}
    assert middle_names == {"t_b", "t_c"}

    # Stage 2: D
    assert len(plan[2]) == 1
    assert plan[2][0].name == "t_d"
~~~~~

### 下一步建议
我们已经修复了所有已知的兼容性问题。现在应该重新运行测试，确认所有组件（Engine, Tools, Tests）都能正常工作。如果一切顺利，就可以提交这个包含并发执行功能的重大更新了。
