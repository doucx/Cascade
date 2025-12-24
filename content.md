好的，我们现在处于 RED 状态，目标明确。是时候实施修复，让测试通过了。

我将生成一个计划，通过引入 `GraphExecutionResult` 数据类来重构 `GraphExecutionStrategy`，从而彻底解决上下文丢失的问题。

## [WIP] fix(engine): 重构 GraphExecutionStrategy 以传递 Jump 上下文

### 错误分析
测试 `test_explicit_jump_from_downstream_task` 的失败根源在于 `GraphExecutionStrategy` 的主执行循环在收到 `Jump` 信号时，丢失了信号来源的上下文。它错误地假设 `Jump` 总是由当前迭代的根任务 (`current_target`) 发出，因此在查找 `ITERATIVE_JUMP` 边时会查看错误的节点，导致 `RuntimeError`。

### 用户需求
重构 `GraphExecutionStrategy`，使其能够准确地追踪 `Jump` 信号的来源节点，并正确地查找绑定在其上的 `ITERATIVE_JUMP` 边，从而使所有显式控制流测试通过。

### 评论
这是解决“战略性矛盾”的典型案例。简单的补丁无法解决问题，我们必须升级核心组件之间的“通信协议”。通过引入 `GraphExecutionResult` 数据类，我们让 `_execute_graph` 和 `_execute_hot_node` 能够向主循环传递更丰富的上下文信息，彻底消除了不健壮的“假设”，使架构更加稳固。

### 目标
1.  在 `graph.py` 中引入一个新的内部数据类 `GraphExecutionResult`，用于封装执行结果值及其来源节点 ID。
2.  修改 `_execute_graph` 和 `_execute_hot_node` 的返回契约，使其返回 `GraphExecutionResult` 实例。
3.  重构 `execute` 方法的主循环，使其能够解包 `GraphExecutionResult`。
4.  在处理 `Jump` 信号时，使用 `GraphExecutionResult.source_node_id` 来无歧义地定位发出信号的节点，并查找正确的跳转边。

### 基本原理
我们将用一个简单的 `dataclass` 来丰富 `_execute_graph` 的返回值，使其从 `Any` 升级为 `GraphExecutionResult(value: Any, source_node_id: str)`。主循环在接收到这个对象后，将同时获得**结果**和**上下文**。当结果是 `Jump` 信号时，它会使用附带的 `source_node_id` 来查找跳转边，确保无论 `Jump` 信号来自执行图的哪个深度，都能被正确路由。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/engine #task/object/graph-strategy #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 引入 GraphExecutionResult 并更新 `_execute_hot_node`

我们在文件顶部定义 `GraphExecutionResult`，并立即更新 `_execute_hot_node` 的返回契约，使其返回这个新类型。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionStrategy:
~~~~~
~~~~~python
from cascade.runtime.constraints.manager import ConstraintManager


@dataclass
class GraphExecutionResult:
    """Internal result carrier to avoid context loss."""

    value: Any
    source_node_id: str


class GraphExecutionStrategy:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        # 3. Minimal State Update (Async)
        await state_backend.put_result(node.structural_id, result)
        return result

    async def _execute_graph(
~~~~~
~~~~~python
        # 3. Minimal State Update (Async)
        await state_backend.put_result(node.structural_id, result)
        return GraphExecutionResult(value=result, source_node_id=node.structural_id)

    async def _execute_graph(
~~~~~

#### Acts 2: 更新 `_execute_graph` 的返回契约

我们修改 `_execute_graph` 内的 `sub_graph_runner` 以解包新返回类型，并修改 `_execute_graph` 自身的最终返回语句以打包成 `GraphExecutionResult`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph
                        sub_graph, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )
~~~~~
~~~~~python
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph
                        sub_graph, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        # The map node expects the raw value, not the result object
                        result_obj = await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )
                        return result_obj.value
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
        # Use the mapped canonical node ID to check for the final result
        if not await state_backend.has_result(target_node.structural_id):
            # For debugging, check if the instance was skipped
            if skip_reason := await state_backend.get_skip_reason(
                target_node.structural_id
            ):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return await state_backend.get_result(target_node.structural_id)
~~~~~
~~~~~python
        # Use the mapped canonical node ID to check for the final result
        if not await state_backend.has_result(target_node.structural_id):
            # For debugging, check if the instance was skipped
            if skip_reason := await state_backend.get_skip_reason(
                target_node.structural_id
            ):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return GraphExecutionResult(
                        value=None, source_node_id=target_node.structural_id
                    )
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        final_value = await state_backend.get_result(target_node.structural_id)
        return GraphExecutionResult(
            value=final_value, source_node_id=target_node.structural_id
        )
~~~~~

#### Acts 3: 重构主执行循环以消除假设

最后，我们重构主 `execute` 循环，使其能够处理 `GraphExecutionResult` 并使用 `source_node_id` 来准确地查找跳转边。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    root_overrides = None
                    if next_input_overrides:
                        root_overrides = next_input_overrides
                        next_input_overrides = None

                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        root_input_overrides=root_overrides,
                    )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            elif isinstance(result, Jump):
                # Handle Explicit Jump
                source_node_id = None
                if target_node := instance_map.get(current_target._uuid):
                    source_node_id = target_node.structural_id

                if not source_node_id and fast_path_data:
                    source_node_id = fast_path_data[2]

                if not source_node_id:
                    raise RuntimeError("Could not locate source node for Jump.")

                # Find outgoing ITERATIVE_JUMP edge
                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.structural_id == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )

                if not jump_edge or not jump_edge.jump_selector:
                    raise RuntimeError(
                        f"Task returned a Jump signal but has no bound 'select_jump' (Edge not found for {source_node_id})."
                    )

                selector = jump_edge.jump_selector
                next_target = selector.routes.get(result.target_key)

                if next_target is None:
                    return result.data

                # Prepare for next iteration
                current_target = next_target

                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}

            else:
                return result
~~~~~
~~~~~python
                # 4. Execute Graph and get a contextual result
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    graph_result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    root_overrides = None
                    if next_input_overrides:
                        root_overrides = next_input_overrides
                        next_input_overrides = None

                    graph_result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        root_input_overrides=root_overrides,
                    )

            # 5. Check for Tail Call & Jumps using the contextual result
            result = graph_result.value

            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            elif isinstance(result, Jump):
                # Handle Explicit Jump using the unambiguous source_node_id
                source_node_id = graph_result.source_node_id

                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.structural_id == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )

                if not jump_edge or not jump_edge.jump_selector:
                    raise RuntimeError(
                        f"Task returned a Jump signal but has no bound 'select_jump' (Edge not found for {source_node_id})."
                    )

                selector = jump_edge.jump_selector
                next_target = selector.routes.get(result.target_key)

                if next_target is None:
                    return result.data

                # Prepare for next iteration
                current_target = next_target

                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}

            else:
                return result
~~~~~

### 下一步建议
我们已经完成了对 `GraphExecutionStrategy` 的核心重构。现在，请再次运行测试。我们期望 `test_explicit_jump_loop` 和 `test_explicit_jump_from_downstream_task` 都能通过，从而将测试套件带回 GREEN 状态。

如果成功，阶段一的核心目标就已达成。
