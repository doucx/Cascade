我将实现递归静态分析和循环检测，以启用复杂 Agent 循环的零开销 TCO 优化。

## [WIP] feat(engine): 实现递归静态分析与 TCO 循环零开销优化

### 用户需求
当前的 TCO 优化仅支持简单的自递归 (`A->A`)。用户需要 Cascade 能够识别并优化复杂的多任务循环 (`A->B->C->A`)，通过编译时的递归静态分析来预先识别循环结构，从而在运行时跳过昂贵的哈希检查。

### 评论
这是一个将 Cascade 的性能从“可用”提升到“高性能”的关键架构变更。通过在 `ast_analyzer` 中引入图论算法（强连通分量检测），我们将智能前移到了编译期，使得运行时引擎能够以近乎原生的速度执行复杂的 Agent 状态机。

### 目标
1.  **增强 `ast_analyzer`**: 实现 `assign_tco_cycle_ids`，使用 Tarjan 算法或 DFS 检测 Task 调用图中的强连通分量 (SCC)，并为处于循环中的 Task 分配统一的 `_tco_cycle_id`。
2.  **升级 `GraphBuilder`**: 使其能够利用 `ast_analyzer` 的结果，递归地构建包含闭环的 Shadow Graph，并将 `tco_cycle_id` 传递给图中的 Node。
3.  **优化 `GraphExecutionStrategy`**: 引入 `_task_templates` 缓存，并实现基于 `tco_cycle_id` 的 O(1) 快速通道，允许引擎在检测到处于同一循环的简单任务转换时，直接复用预编译的图模板。

### 基本原理
-   **静态分析 (Static Analysis)**: 利用 Python 的 AST 能力，我们可以构建出 Task 之间的静态调用图。
-   **SCC 检测**: 调用图中的环（Cycle）对应于图论中的强连通分量。处于同一个 SCC 中的所有任务实际上构成了一个大的递归闭包。
-   **身份对齐 (Identity Alignment)**: 通过给这些任务打上相同的 ID，我们在运行时创造了一个极其廉价的检查机制 (`id_a == id_b`)，用来替代昂贵的结构哈希 (`hash(graph_a) == hash(graph_b)`)。

### 标签
#intent/perf #flow/ready #priority/high #comp/engine #comp/graph #concept/tco #scope/core #ai/instruct #task/domain/engine #task/object/tco-loop #task/action/optimize #task/state/begin

---

### Script

#### Acts 1: 增强 AST 分析器以支持循环检测

我们在 `cascade/graph/ast_analyzer.py` 中引入 `assign_tco_cycle_ids` 函数。它使用深度优先搜索 (DFS) 来遍历任务调用链，识别循环，并为循环中的任务生成稳定的 ID。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/ast_analyzer.py
~~~~~
~~~~~python
def analyze_task_source(task_func: Callable) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    """
    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError) as e:
        logger.warning(f"Could not parse source for {task_func.__name__}: {e}")
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    return list(visitor.potential_targets)
~~~~~
~~~~~python
def analyze_task_source(task_func: Callable) -> List[Task]:
    """
    Analyzes a task function's source code to find potential TCO targets.
    """
    try:
        source = inspect.getsource(task_func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
    except (OSError, SyntaxError) as e:
        logger.warning(f"Could not parse source for {task_func.__name__}: {e}")
        return []

    resolver = ReferenceResolver(task_func)
    visitor = TcoVisitor(resolver)
    visitor.visit(tree)

    return list(visitor.potential_targets)


def assign_tco_cycle_ids(root_task: Task) -> None:
    """
    Performs a recursive static analysis starting from root_task to identify
    Strongly Connected Components (cycles) in the task call graph.

    If a cycle is detected (e.g., A -> B -> A), a unique 'tco_cycle_id' is
    generated and assigned to the '_tco_cycle_id' attribute of all Tasks
    involved in that cycle.

    This enables the Engine to recognize multi-task TCO loops at runtime.
    """
    # Use a simple DFS to detect cycles
    visited = set()
    recursion_stack = set()
    path: List[Task] = []

    def _dfs(current_task: Task):
        visited.add(current_task)
        recursion_stack.add(current_task)
        path.append(current_task)

        # Get static targets (memoize if needed, but analyze_task_source is fast enough)
        targets = analyze_task_source(current_task.func)

        for target in targets:
            if target not in visited:
                _dfs(target)
            elif target in recursion_stack:
                # Cycle Detected!
                # All tasks in path from 'target' to 'current_task' form the cycle.
                try:
                    start_index = path.index(target)
                    cycle_members = path[start_index:]
                    
                    # Generate a deterministic ID for this cycle
                    # Sort names to ensure stability regardless of entry point
                    member_names = sorted(t.name for t in cycle_members if t.name)
                    cycle_signature = "|".join(member_names)
                    # Use a simple hash of the signature
                    import hashlib
                    cycle_id = hashlib.md5(cycle_signature.encode()).hexdigest()

                    for member in cycle_members:
                        # Only overwrite if not set or allow merging? 
                        # For simplicity, last write wins or check consistency.
                        member._tco_cycle_id = cycle_id

                except ValueError:
                    pass

        recursion_stack.remove(current_task)
        path.pop()

    _dfs(root_task)
~~~~~

#### Acts 2: 更新 GraphBuilder 以构建递归 Shadow Graph

修改 `GraphBuilder`，使其在构建图时利用 `assign_tco_cycle_ids` 的结果。如果发现 TCO 标记，它将递归地构建 Shadow Nodes，并在图中创建闭环（`POTENTIAL` 边指向已存在的节点），从而形成完整的静态全景图。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.graph.ast_analyzer import analyze_task_source


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
~~~~~
~~~~~python
from cascade.graph.ast_analyzer import analyze_task_source, assign_tco_cycle_ids
from cascade.spec.task import Task


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}
        # Used to detect cycles during shadow node expansion
        self._shadow_visited: Dict[Task, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # Check cache on Task object to avoid re-parsing AST
            if getattr(result.task, "_potential_tco_targets", None) is None:
                result.task._potential_tco_targets = analyze_task_source(
                    result.task.func
                )

            potential_targets = result.task._potential_tco_targets
            for target_task in potential_targets:
                potential_uuid = f"potential:{result._uuid}:{target_task.name}"

                # Shadow nodes are created by directly instantiating Node,
                # not by visiting the LazyResult, to mark them explicitly.
                # This avoids them being added to the `_visited` cache with a real UUID.
                target_node = Node(
                    id=potential_uuid,
                    name=target_task.name,
                    node_type="task",
                    is_shadow=True,  # Explicitly mark as a shadow node
                )
                self.graph.add_node(target_node)
                self._visited[potential_uuid] = target_node

                edge = Edge(
                    source=node,
                    target=target_node,
                    arg_name="<potential>",
                    edge_type=EdgeType.POTENTIAL,
                )
                self.graph.add_edge(edge)

        return node
~~~~~
~~~~~python
        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # 6.1 Analyze and tag cycles if not already done
            if getattr(result.task, "_tco_cycle_id", None) is None:
                assign_tco_cycle_ids(result.task)
            
            # Propagate cycle ID to the Node
            node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

            # 6.2 Check cache on Task object to avoid re-parsing AST
            if getattr(result.task, "_potential_tco_targets", None) is None:
                result.task._potential_tco_targets = analyze_task_source(
                    result.task.func
                )

            potential_targets = result.task._potential_tco_targets
            
            # Register current node in shadow map to allow closing the loop back to root
            self._shadow_visited[result.task] = node

            for target_task in potential_targets:
                self._visit_shadow_recursive(node, target_task)

        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        """
        Recursively builds shadow nodes for static analysis.
        If a task is already in the graph (either as a real node or shadow node),
        it creates a POTENTIAL edge pointing to it, closing the loop.
        """
        # If we have already visited this task in this build context, link to it
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            edge = Edge(
                source=parent_node,
                target=target_node,
                arg_name="<potential>",
                edge_type=EdgeType.POTENTIAL,
            )
            self.graph.add_edge(edge)
            return

        # Otherwise, create a new Shadow Node
        # We use a deterministic ID based on the task name to allow some stability,
        # but prefixed to avoid collision with real nodes.
        potential_uuid = f"shadow:{parent_node.id}:{task.name}"
        
        target_node = Node(
            id=potential_uuid,
            name=task.name,
            node_type="task",
            is_shadow=True,
            tco_cycle_id=getattr(task, "_tco_cycle_id", None)
        )
        self.graph.add_node(target_node)
        
        # Register in visited map
        self._shadow_visited[task] = target_node

        edge = Edge(
            source=parent_node,
            target=target_node,
            arg_name="<potential>",
            edge_type=EdgeType.POTENTIAL,
        )
        self.graph.add_edge(edge)

        # Recursively expand its potential targets
        if getattr(task, "_potential_tco_targets", None) is None:
            task._potential_tco_targets = analyze_task_source(task.func)
        
        for next_task in task._potential_tco_targets:
            self._visit_shadow_recursive(target_node, next_task)
~~~~~

#### Acts 3: 在 Node 模型中增加 tco_cycle_id 字段

更新 `Node` 数据类以支持新的元数据。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only

    # Core spec
~~~~~
~~~~~python
    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
~~~~~

#### Acts 4: 升级 GraphExecutionStrategy 实现 O(1) 快速通道

这是本次优化的核心。我们引入 `_task_templates` 缓存，并在 `execute` 循环中检测：如果当前任务与上一个任务共享相同的 `tco_cycle_id`（意味着它们在同一个预定义的静态循环中），且当前任务结构简单，则直接从缓存中实例化图模板，跳过 `StructuralHasher`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
~~~~~
~~~~~python
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Cache for structural hashing (slow path)
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}
        # Cache for Zero-Overhead TCO (fast path), keyed by Task object
        self._task_templates: Dict[Any, Tuple[Graph, Any]] = {}

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        # Optimization state for TCO Fast Path
        last_executed_task = None
        last_graph = None
        last_plan = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph = None
                plan = None
                literals = None

                # --- FAST PATH CHECK ---
                is_fast_path = False
                if (
                    last_executed_task is not None
                    and last_graph is not None
                    and isinstance(current_target, LazyResult)
                    and current_target.task == last_executed_task
                ):
                    if self._is_simple_task(current_target):
                        is_fast_path = True
                        graph = last_graph
                        plan = last_plan
                        # Update literals in O(1) without hashing
                        self._update_graph_literals(graph, current_target, {})

                if not is_fast_path:
                    # --- SLOW PATH (Hashing & Cache) ---
                    # 1. Get Graph and Plan, using Structural Hash Cache
                    hasher = StructuralHasher()
                    struct_hash, literals = hasher.hash(current_target)

                    if struct_hash in self._graph_cache:
                        # CACHE HIT: Reuse graph and plan
                        cached_graph, cached_plan = self._graph_cache[struct_hash]
                        if len(cached_graph.nodes) > 1:
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                        else:
                            graph = cached_graph
                            plan = cached_plan
                            self._update_graph_literals(graph, current_target, literals)
                    else:
                        # CACHE MISS: Build, solve, and cache
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                        self._graph_cache[struct_hash] = (graph, plan)

                    # Update cache for next iteration possibility
                    last_graph = graph
                    last_plan = plan
~~~~~
~~~~~python
        # Optimization state for TCO Fast Path
        last_executed_task = None
        last_tco_cycle_id = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph = None
                plan = None
                literals = None
                is_fast_path = False

                # --- 1. ZERO-OVERHEAD FAST PATH CHECK ---
                # Check if we are in a recognized TCO loop (A -> B -> ... -> A)
                # Conditions:
                # 1. Target is a LazyResult and "simple" (no complex deps).
                # 2. Target task has been statically analyzed as part of a TCO cycle.
                # 3. We have a compiled template for this task.
                # 4. (Optional but safe) The previous task was also part of a cycle (or we are starting one).
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)
                    
                    # If we have a cycle match or self-recursion match
                    if (cycle_id and cycle_id == last_tco_cycle_id) or (task_obj == last_executed_task):
                        if task_obj in self._task_templates:
                            is_fast_path = True
                            graph, plan = self._task_templates[task_obj]
                            # Update literals in O(1) without hashing
                            self._update_graph_literals(graph, current_target, {})
                
                if not is_fast_path:
                    # --- 2. SLOW PATH (Hashing & Cache) ---
                    # Get Graph and Plan, using Structural Hash Cache
                    hasher = StructuralHasher()
                    struct_hash, literals = hasher.hash(current_target)

                    if struct_hash in self._graph_cache:
                        # CACHE HIT: Reuse graph and plan
                        cached_graph, cached_plan = self._graph_cache[struct_hash]
                        if len(cached_graph.nodes) > 1:
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                        else:
                            graph = cached_graph
                            plan = cached_plan
                            self._update_graph_literals(graph, current_target, literals)
                    else:
                        # CACHE MISS: Build, solve, and cache
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                        self._graph_cache[struct_hash] = (graph, plan)
                        
                        # Populate Task Template Cache if this is a simple node
                        # This "warms up" the fast path for future iterations
                        if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                             self._task_templates[current_target.task] = (graph, plan)

                # Update state for next iteration
                if isinstance(current_target, LazyResult):
                    last_executed_task = current_target.task
                    last_tco_cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
                else:
                    last_executed_task = None
                    last_tco_cycle_id = None
~~~~~

#### Acts 5: 添加互递归 TCO 测试用例

添加一个新的测试文件 `tests/engine/runtime/test_tco_mutual_recursion.py`，验证 `A->B->A` 这种互递归场景下的 TCO 是否正常工作，且不会引发栈溢出。

~~~~~act
write_file
tests/engine/runtime/test_tco_mutual_recursion.py
~~~~~
~~~~~python
import sys
import pytest
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

@pytest.fixture
def engine():
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

@pytest.mark.asyncio
async def test_mutual_recursion_tco_optimization(engine):
    """
    Verifies that mutual recursion (A -> B -> A) is optimized via TCO.
    If the engine builds a new graph for every step without releasing memory/stack,
    or if it fails to use the fast path, this might be slow or crash on low-resource envs.
    
    But primarily we check correctness here. The O(1) property is verified by 
    inspecting internal cache behavior if we wanted to be deeper.
    """
    
    # Increase depth to ensure we exceed default stack limits if TCO fails
    # Standard Python recursion limit is 1000. We do 2000 steps (1000 loops).
    sys.setrecursionlimit(1500)
    TOTAL_STEPS = 2000

    @cs.task
    def task_a(n: int):
        if n <= 0:
            return "Done"
        return task_b(n - 1)

    @cs.task
    def task_b(n: int):
        if n <= 0:
            return "Done"
        return task_a(n - 1)

    # Force analysis to ensure cycle IDs are assigned (though engine should do it)
    # from cascade.graph.ast_analyzer import assign_tco_cycle_ids
    # assign_tco_cycle_ids(task_a)
    
    result = await engine.run(task_a(TOTAL_STEPS))
    assert result == "Done"

    # Verify that cycle IDs were assigned
    assert getattr(task_a, "_tco_cycle_id", None) is not None
    assert getattr(task_b, "_tco_cycle_id", None) is not None
    assert getattr(task_a, "_tco_cycle_id") == getattr(task_b, "_tco_cycle_id")
~~~~~

### 下一步建议
我们已经实现了 TCO 循环的零开销优化。接下来的重点可以放在**可视化**上：
1.  **cs.visualize**: 利用 `tco_cycle_id` 和 Shadow Graph，在生成的 DOT 图中将 `POTENTIAL` 边渲染为带有明显样式的虚线（例如 `color=gray, style=dashed`），并尝试将整个循环渲染在一个 `subgraph cluster` 中，从而直观地展示 Agent 的状态机闭环。
2.  **静态死循环检测**: 利用 `GraphBuilder` 构建的完整图，检测是否存在没有“出口”（所有路径都回到循环内）的纯闭环，并在运行前发出警告。
