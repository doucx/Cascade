## [WIP] fix(runtime): Fix result mapping misalignment in Engine due to dynamic pruning

### 用户需求
修复 `Engine` 中的一个严重 Bug：当并行执行的任务触发了剪枝逻辑（例如 `Router` 的 Selector 完成），可能会导致同一批次中正在运行的其他任务被标记为 `Skipped`。这导致在结果收集阶段，`runnable_nodes` 列表（过滤掉了 Skipped 节点）与 `stage_results` 列表（包含所有已运行任务的结果）长度和顺序不一致，从而导致结果错位（Zip Misalignment）。

### 评论
这个 Bug 非常隐蔽且致命。它揭示了“执行计划状态”在异步并发环境下的易变性。我们不能依赖“再次过滤”来重建上下文，必须在提交任务时就确立好“任务 -> 节点”的不可变映射关系。

### 目标
修改 `Engine._execute_graph` 方法，在构建 `tasks_to_run` 的同时，同步构建一个 `nodes_in_execution` 列表。在收集结果时，直接使用这个列表进行 Zip 操作，完全摒弃重新过滤的逻辑。

### 基本原理
通过维护一个显式的 `nodes_in_execution` 列表，我们确保了无论任务执行期间发生了什么状态变更（如剪枝），结果与其所属节点的对应关系始终是锚定的、正确的。即使一个任务在运行期间被标记为 Pruned，既然它已经运行并产生了结果，我们就应该记录这个结果（或者丢弃），但绝不能让它影响其他节点的结果映射。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/engine #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修复 `Engine` 的结果映射逻辑

我们将在 `_execute_graph` 中引入 `nodes_in_execution` 列表，确保结果的一一对应。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self.flow_manager.should_skip(node, results)
                if skip_reason:
                    self.flow_manager.mark_skipped(node.id)
                    self.bus.publish(
                        TaskSkipped(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            reason=skip_reason,
                        )
                    )
                    continue
                
                # Create coroutine for the node
                tasks_to_run.append(
                    self._execute_node_with_policies(
                        node, graph, results, active_resources, run_id, params
                    )
                )

            if not tasks_to_run:
                continue

            # Execute stage in parallel
            # We use return_exceptions=False (default) so the first error propagates immediately
            stage_results = await asyncio.gather(*tasks_to_run)

            # Map results back to node IDs
            # We need to reconstruct which result belongs to which node
            # tasks_to_run order matches the iteration order.
            # We need to re-iterate or capture the mapping.
            # Let's capture the node IDs corresponding to tasks_to_run.
            
            runnable_nodes = []
            for node in stage:
                if node.node_type != "param" and not self.flow_manager.is_skipped(node.id):
                    runnable_nodes.append(node)
            
            for node, res in zip(runnable_nodes, stage_results):
                results[node.id] = res
~~~~~
~~~~~python
        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
            nodes_in_execution = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self.flow_manager.should_skip(node, results)
                if skip_reason:
                    self.flow_manager.mark_skipped(node.id)
                    self.bus.publish(
                        TaskSkipped(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            reason=skip_reason,
                        )
                    )
                    continue
                
                # Create coroutine for the node
                tasks_to_run.append(
                    self._execute_node_with_policies(
                        node, graph, results, active_resources, run_id, params
                    )
                )
                nodes_in_execution.append(node)

            if not tasks_to_run:
                continue

            # Execute stage in parallel
            # We use return_exceptions=False (default) so the first error propagates immediately
            stage_results = await asyncio.gather(*tasks_to_run)

            # Map results back to node IDs
            # We use the captured nodes_in_execution list to ensure 1:1 mapping with tasks_to_run.
            # This is critical because tasks executing in parallel might trigger pruning (via Router),
            # which could change the skip status of nodes in this very list.
            # If we re-filtered based on skip status here, we'd get a misalignment.
            for node, res in zip(nodes_in_execution, stage_results):
                results[node.id] = res
~~~~~

### 下一步建议
这是一个涉及并发一致性的关键修复。
现在，即使 `Router` 剪枝了当前批次中的某个任务，该任务的结果仍然会与其节点正确对应（因为它是基于提交时的快照）。虽然从业务逻辑上看这个结果可能不再被需要（因为被剪枝了），但从引擎的数据一致性角度看，它必须被正确归档，不能“张冠李戴”。

请运行测试。验证通过后，我们的 `Router` 和 `FlowManager` 实现就可以视为稳固了。
