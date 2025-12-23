好的，我分析了测试失败的原因。问题出在我上次重构 `GraphBuilder` 时引入的一个设计缺陷。

错误分析

**根本原因**：`GraphBuilder` 的重构引入了两种类型的 ID：
1.  **实例 ID (`LazyResult._uuid`)**: 唯一标识一次特定的任务调用。
2.  **结构化 ID (`Node.id`, 即 shallow_hash)**: 唯一标识一个任务的“模板”或“原型”。

然而，`GraphExecutionStrategy` 的执行逻辑没有完全适配这个变化。它在 `state_backend` 中使用**结构化 ID** 存储任务结果，但在最后获取最终工作流结果时，却错误地使用了**实例 ID** 去查询，导致了大量的 `KeyError`。

此外，`FlowManager`（流程管理器）的初始化也使用了错误的 ID，这导致了不正确的依赖需求计算和错误的剪枝（Pruning），从而引发了下游的 `DependencyMissingError`。

**解决方案**：
我将通过以下步骤修复这个问题：
1.  修改 `build_graph` 函数，让它在构建图的同时，返回一个从“实例 ID”到“结构化 ID 对应节点”的映射表。
2.  更新 `GraphExecutionStrategy` 来使用这个映射表，确保在初始化 `FlowManager` 和查询最终结果时，都使用正确的**结构化 ID**。

这个修复将使整个执行流程中的 ID 使用保持一致，解决所有相关的测试失败。

## [WIP] fix(engine): Correct ID usage in executor for node interning

### 错误分析
在引入节点复用（interning）后，`Node.id` 变为了一个基于其浅层结构的哈希值，而 `LazyResult._uuid` 仍然是唯一的实例标识符。`GraphExecutionStrategy` 未能正确处理这两种 ID，导致在 `state_backend` 中存取结果时使用了不一致的键。具体来说，它使用 `Node.id`（结构化哈希）存入结果，却用 `LazyResult._uuid`（实例 ID）查询最终结果，导致 `KeyError`。此问题也影响了 `FlowManager` 的初始化，造成了错误的依赖剪枝，引发了 `DependencyMissingError`。

### 用户需求
修复因节点复用（Node Interning）重构引入的 ID 不匹配问题，使测试套件恢复正常。

### 评论
这是一个典型的重构后集成问题。核心数据模型（`Node`）的身份语义发生了变化，但执行层的一个关键部分没有相应更新。这个修复将使执行策略与新的图构建模型保持同步，是完成“节点复用”功能的关键一步。

### 目标
1.  调整 `build_graph` 的返回值，使其额外提供一个 `LazyResult._uuid` 到 `Node` 对象的映射。
2.  修改 `GraphExecutionStrategy` 以消费此映射，确保在整个执行周期中使用正确的 `Node.id` 与 `state_backend` 和 `FlowManager` 交互。
3.  使所有失败的测试通过。

### 基本原理
我们将 `GraphBuilder` 构建过程中产生的 `_visited_instances` 映射（从 `_uuid` 到 `Node`）传递给 `GraphExecutionStrategy`。执行器将利用此映射，在需要引用特定 `LazyResult` 实例（如工作流的最终目标）时，能够准确地找到其对应的、具有结构化 ID 的 `Node` 对象，从而使用正确的键从 `state_backend` 中获取结果。

### 标签
#intent/fix #flow/ready #priority/critical #comp/graph #comp/engine #concept/interning #scope/core #ai/instruct #task/domain/testing #task/object/test-failures #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 ID 使用不一致问题

我们将首先修改 `build.py`，让 `build_graph` 返回 ID 映射。然后，更新 `strategies.py` 中的 `GraphExecutionStrategy` 来正确使用这个映射。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer)
~~~~~
~~~~~python
    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
def build_graph(target: Any, registry: NodeRegistry | None = None) -> Tuple[Graph, Tuple[Any, ...]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~python
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                if not is_fast_path:
                    # --- 2. STANDARD PATH ---
                    # Always build fresh for now to handle data extraction
                    graph, data_tuple = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    # Store in template cache for future optimization (even if we don't fully use it yet)
                    if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                        self._task_templates[current_target.task] = (graph, plan)
~~~~~
~~~~~python
                if not is_fast_path:
                    # --- 2. STANDARD PATH ---
                    # Always build fresh for now to handle data extraction
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    # Store in template cache for future optimization (even if we don't fully use it yet)
                    if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                        self._task_templates[current_target.task] = (graph, plan)
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple, # Pass the blood!
                    plan,
                )
~~~~~
~~~~~python
                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,  # Pass the blood!
                    plan,
                    instance_map,
                )
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        data_tuple: Tuple[Any, ...],
        plan: Any,
    ) -> Any:
        flow_manager = FlowManager(graph, target._uuid)
        blocked_nodes = set()

        for stage in plan:
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        data_tuple: Tuple[Any, ...],
        plan: Any,
        instance_map: Dict[str, Node],
    ) -> Any:
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id)
        blocked_nodes = set()

        for stage in plan:
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            data_tuple=sub_data,
                            plan=sub_plan,
                        )
~~~~~
~~~~~python
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            data_tuple=sub_data,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )
~~~~~
~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                # A skip due to a sequence aborting is a valid, graceful termination.
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)
~~~~~
~~~~~python
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not state_backend.has_result(target_node.id):
            # For debugging, check if the instance was skipped
            if skip_reason := state_backend.get_skip_reason(target_node.id):
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

        return state_backend.get_result(target_node.id)
~~~~~

### 下一步建议
我们已经修复了由于 `Node` ID 语义变化导致的执行器错误。现在，我将再次运行测试套件，以验证这些修复是否解决了所有相关问题，并确保系统恢复到稳定状态。
