这是一个非常核心的架构升级。在实现 `CSPSolver` 之前，我们需要先重构 `Engine` 和 `ExecutionPlan` 协议，使其支持**分层并行执行 (Batched/Staged Execution)**。目前的 `Engine` 严格串行执行任务，这限制了 `Cascade` 的性能，也使得高级调度器没有用武之地。

我们将分两步走：
1.  **架构升级**: 重构 `Engine` 和 `NativeSolver`，支持 `List[List[Node]]` 形式的分层执行计划。这将立即为用户带来并行执行的能力。
2.  **高级调度**: 引入 `CSPSolver`，在分层的基础上加入资源约束优化。

现在开始第一步。

## [WIP] feat(runtime): Enable parallel execution via staged execution plan

### 用户需求
当前的 `Engine` 是串行执行任务的。即使两个任务之间没有依赖关系，它们也会一个接一个地运行。用户希望能够并行执行无依赖的任务，以提高工作流的总吞吐量。

### 评论
这是 `Cascade` 演进过程中的一个重要里程碑。通过将 `ExecutionPlan` 从扁平的 `List[Node]` 升级为分层的 `List[List[Node]]`，我们为真正的并发执行打开了大门。这也为后续的 `CSPSolver` 提供了必要的运行时基础——Solver 将负责规划“哪些任务应该在同一层并行”。

### 目标
1.  更新 `src/cascade/runtime/protocols.py` 中的 `ExecutionPlan` 类型定义。
2.  重写 `src/cascade/adapters/solvers/native.py`，实现分层拓扑排序算法，尽可能将无依赖的任务放在同一层。
3.  重构 `src/cascade/runtime/engine.py` 的 `_execute_graph` 方法，使用 `asyncio.gather` 并发执行每一层中的任务。

### 基本原理
我们采用 **分层执行 (Staged Execution)** 模型。
*   **Solver**: 负责生成层级。对于 `NativeSolver`，它将使用贪婪策略，将所有当前入度为 0 的节点放入同一层。
*   **Engine**: 负责执行层级。它会按顺序遍历层级，但对于层级内的所有任务，会同时启动并等待它们全部完成（Barrier）。
虽然这种模型存在“同步屏障”问题（一层中最慢的任务会拖慢整体进度），但它实现简单、确定性强，且与我们未来的静态资源调度 (CSP) 路线图完美契合。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #comp/engine #concept/concurrency #scope/core
#ai/instruct
#task/domain/runtime #task/object/execution-plan #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 更新协议定义

修改 `protocols.py`，将 `ExecutionPlan` 定义为嵌套列表。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict
from cascade.graph.model import Graph, Node

# An execution plan is simply an ordered list of nodes to execute.
ExecutionPlan = List[Node]


class Solver(Protocol):
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict
from cascade.graph.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List[Node]]


class Solver(Protocol):
~~~~~

#### Acts 2: 升级 NativeSolver 实现分层排序

修改 `native.py`。由于 `graphlib.TopologicalSorter` 不直接支持分层输出，我们将手动实现一个基于入度表的分层 Kahn 算法。

~~~~~act
patch_file
src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python
from graphlib import TopologicalSorter
from typing import Dict
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan


class NativeSolver:
    """
    A solver that uses Python's standard library `graphlib` to produce
    a sequential execution plan.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Create a mapping from node ID to node object for quick lookup
        node_map: Dict[str, Node] = {node.id: node for node in graph.nodes}

        # Build the dependency structure for TopologicalSorter
        # Format: {node_id: {dep1_id, dep2_id, ...}}
        deps: Dict[str, set] = {node.id: set() for node in graph.nodes}
        for edge in graph.edges:
            deps[edge.target.id].add(edge.source.id)

        # Perform the sort
        ts = TopologicalSorter(deps)
        sorted_node_ids = list(ts.static_order())

        # Map sorted IDs back to Node objects
        plan = [node_map[node_id] for node_id in sorted_node_ids]
        return plan
~~~~~
~~~~~python
from typing import Dict, List, Set
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan


class NativeSolver:
    """
    A solver that produces a staged execution plan (layered topological sort).
    Nodes in the same stage have no dependencies on each other and can be run in parallel.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # 1. Calculate in-degrees for all nodes
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        adj_list: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}

        for edge in graph.edges:
            in_degree[edge.target.id] += 1
            adj_list[edge.source.id].append(edge.target.id)

        # 2. Identify initial layer (nodes with 0 in-degree)
        current_stage = [node for node in graph.nodes if in_degree[node.id] == 0]
        
        # Sort stage by name for deterministic behavior
        current_stage.sort(key=lambda n: n.name)

        plan: ExecutionPlan = []
        processed_count = 0

        while current_stage:
            plan.append(current_stage)
            processed_count += len(current_stage)
            next_stage_nodes: Set[str] = set()

            # 3. Simulate execution of current stage
            for node in current_stage:
                # For each downstream neighbor
                for neighbor_id in adj_list[node.id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        next_stage_nodes.add(neighbor_id)
            
            # Prepare next stage
            # We need to map IDs back to Node objects. 
            # Optimization: could use a lookup dict, but graph.nodes is usually small enough.
            # Let's create a lookup for speed.
            node_lookup = {n.id: n for n in graph.nodes}
            
            next_stage = [node_lookup[nid] for nid in next_stage_nodes]
            next_stage.sort(key=lambda n: n.name) # Deterministic
            
            current_stage = next_stage

        # 4. Cycle detection
        if processed_count < len(graph.nodes):
             # Finding the cycle is complex, for now raise a generic error
             raise ValueError("Cycle detected in the dependency graph.")

        return plan
~~~~~

#### Acts 3: 重构 Engine 支持并发执行

修改 `engine.py`。主循环现在将遍历 stages，并使用 `asyncio.gather` 并发执行每个 stage 中的节点。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        graph = build_graph(target)
        plan = self.solver.resolve(graph)
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()

        self._inject_params(plan, params, results)

        for node in plan:
            if node.node_type == "param":
                continue

            skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
            if skip_reason:
                skipped_node_ids.add(node.id)
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason=skip_reason,
                    )
                )
                continue

            # Execute Node
            results[node.id] = await self._execute_node_with_policies(
                node, graph, results, active_resources, run_id, params
            )

        # Final check: Was the target task executed?
~~~~~
~~~~~python
    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        graph = build_graph(target)
        plan = self.solver.resolve(graph)  # Now returns List[List[Node]]
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()

        # Inject params first (usually params are in the first stage or handled implicitly)
        # We need to flatten the plan to find params or iterate carefully.
        # Let's just iterate:
        all_nodes = [node for stage in plan for node in stage]
        self._inject_params(all_nodes, params, results)

        for stage in plan:
            # Prepare tasks for this stage
            tasks_to_run = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
                if skip_reason:
                    skipped_node_ids.add(node.id)
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
                if node.node_type != "param" and node.id not in skipped_node_ids:
                    runnable_nodes.append(node)
            
            for node, res in zip(runnable_nodes, stage_results):
                results[node.id] = res

        # Final check: Was the target task executed?
~~~~~

### 下一步建议
我们已经完成了并发执行的核心重构。现在需要运行现有的测试套件，特别是 `tests/adapters/solvers/test_native.py`（它测试了求解器的输出结构，现在结构变了，测试肯定会挂）和 `tests/integration`。我们需要更新 `test_native.py` 以适配新的分层结构。
