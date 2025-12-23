简要回答
是的，我将通过引入基于索引的计划缓存机制，将 `template_id` 实际上投入使用。这将允许不同数据的同构图共享同一个执行计划模板，从而大幅提升复杂递归任务的性能。

## [WIP] feat(engine): 实现基于 Template ID 的索引化 Plan 缓存

### 用户需求
用户希望 `GraphExecutionStrategy` 能够利用新引入的 `template_id` 来复用执行计划（Execution Plan）。目前的缓存机制是基于具体的 `Node.id`，这导致每次参数变化（如 `f(10)` -> `f(9)`）都会被视为缓存未命中，无法利用已有的拓扑排序结果。

### 评论
这是一个非常巧妙的优化。通过将 `ExecutionPlan` 抽象为“节点索引的列表”（即 `List[List[int]]`），我们解耦了计划的结构与具体的节点实例。结合 `template_id`，这使得 Cascade 能够像 Hashlife 算法一样，对所有结构相同的计算图只进行一次“编译”（Solver 解析），极大地降低了运行时开销。

### 目标
1.  在 `GraphExecutionStrategy` 中引入 `IndexedExecutionPlan` 概念（`List[List[int]]`）。
2.  实现 `_index_plan` 方法：将 Solver 生成的 `ExecutionPlan` 转换为索引形式。
3.  实现 `_rehydrate_plan` 方法：将缓存的索引计划应用到当前构建的 `Graph` 实例上，还原为可执行的 `ExecutionPlan`。
4.  升级主执行循环：使用 `root_node.template_id` 作为缓存键，实现“一次编译，多次运行”。

### 基本原理
1.  **确定性遍历**: `GraphBuilder` 使用后序遍历构建图，因此对于结构相同的图，其 `graph.nodes` 列表中的节点顺序是确定且一致的。
2.  **索引映射**: 利用上述特性，我们可以安全地用“节点在 `graph.nodes` 中的索引”来代表节点在计划中的位置。
3.  **模板复用**: `f(10)` 和 `f(9)` 虽然生成不同的 `Node` 对象，但它们拥有相同的 `template_id` 且图结构同构。因此，`f(10)` 计算出的索引计划（如 `[[0], [1]]`）可以直接应用在 `f(9)` 的图实例上。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/cache #scope/core #ai/instruct #task/domain/core #task/object/execution-strategy #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 升级 `GraphExecutionStrategy`

我们将修改 `cascade-engine` 中的 `graph.py`，实现上述的索引化缓存逻辑。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps structural hash (root_node_id) to a compiled ExecutionPlan
        self._plan_cache: Dict[str, ExecutionPlan] = {}
        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, instance_map = build_graph(
                    current_target, registry=self._node_registry
                )

                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )
                target_node = instance_map[current_target._uuid]
                root_node_id = target_node.id

                # 2. Resolve Plan (With JIT Caching)
                if root_node_id in self._plan_cache:
                    # Hit: Reuse the existing plan directly.
                    # Since we use a persistent NodeRegistry, the Nodes in this plan are valid for the current graph.
                    plan = self._plan_cache[root_node_id]
                else:
                    # Miss: Ask solver to resolve and then cache it.
                    plan = self.solver.resolve(graph)
                    self._plan_cache[root_node_id] = plan

                # 3. Setup Resources (mixed scope)
~~~~~
~~~~~python
    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        """
        Converts a Plan (List[List[Node]]) into an IndexedPlan (List[List[int]]).
        The index corresponds to the node's position in graph.nodes.
        """
        # Create a fast lookup for node indices
        id_to_idx = {node.id: i for i, node in enumerate(graph.nodes)}
        indexed_plan = []
        for stage in plan:
            # Map each node in the stage to its index in the graph
            indexed_stage = [id_to_idx[node.id] for node in stage]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        """
        Converts an IndexedPlan back into a Plan using the nodes from the current graph.
        """
        plan = []
        for stage_indices in indexed_plan:
            # Map indices back to Node objects from the current graph instance
            stage_nodes = [graph.nodes[idx] for idx in stage_indices]
            plan.append(stage_nodes)
        return plan

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, instance_map = build_graph(
                    current_target, registry=self._node_registry
                )

                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(
                        f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                    )
                target_node = instance_map[current_target._uuid]
                
                # Use template_id for caching. Fallback to id if template_id is missing (should not happen).
                cache_key = target_node.template_id or target_node.id

                # 2. Resolve Plan (With JIT Template Caching)
                if cache_key in self._template_plan_cache:
                    # Hit: Rehydrate the indexed plan using the current graph's nodes.
                    indexed_plan = self._template_plan_cache[cache_key]
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    # Miss: Ask solver to resolve.
                    plan = self.solver.resolve(graph)
                    # Index and cache the plan for future reuse.
                    self._template_plan_cache[cache_key] = self._index_plan(graph, plan)

                # 3. Setup Resources (mixed scope)
~~~~~

### 下一步建议
我们已经完成了缓存逻辑的升级。现在，`tco_performance.py` 中的 `heavy_complex_countdown` 应该会表现出显著的性能提升。下一步，我们应该运行基准测试来验证这一改进。
