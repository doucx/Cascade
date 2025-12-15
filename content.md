## [WIP] feat: 实现核心协议与默认适配器 (Solver & Executor)

### 用户需求
执行 Cascade 阶段一 (MVP) 的第 5 步：
1.  **定义协议**: 在 `cascade/runtime/protocols.py` 中定义 `Solver` 和 `Executor` 协议。
2.  **实现求解器**: 实现一个 `NativeSolver`，使用 `graphlib` 进行拓扑排序。
3.  **实现执行器**: 实现一个 `LocalExecutor`，用于在本地同步执行任务。
4.  **测试**: 编写测试用例验证 `Solver` 和 `Executor` 的功能。

### 评论
这是将静态的计算图转化为可执行计划的关键一步。`Solver` 负责“思考”做什么（What），而 `Executor` 负责“执行”怎么做（How）。通过协议将它们解耦，为未来引入并行执行器（`DaskExecutor`）或约束求解器（`CSPSolver`）奠定了坚实的基础。

### 目标
1.  创建 `src/cascade/runtime/protocols.py`。
2.  创建 `src/cascade/adapters/solvers/native.py`。
3.  创建 `src/cascade/adapters/executors/local.py`。
4.  创建 `tests/test_adapters.py`。

### 基本原理
*   **协议优先**: 首先定义清晰的接口，实现细节隐藏在适配器中。
*   **零依赖**: 默认的 `NativeSolver` 和 `LocalExecutor` 仅依赖 Python 标准库，符合 MVP 原则。
*   **职责分离**:
    *   `NativeSolver` 只关心图的结构，输出一个有序的节点列表。
    *   `LocalExecutor` 只关心单个节点的执行，它通过查询图的边来动态地构建函数的参数。

### 标签
#intent/build #flow/ready #priority/high
#task/domain/runtime #task/object/execution-engine #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 定义运行时协议 (Protocols)

创建 `Solver` 和 `Executor` 的接口定义。我们还需要一个 `ExecutionPlan` 类型来表示求解器的输出。

~~~~~act
write_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Any, Dict
from cascade.graph.model import Graph, Node

# An execution plan is simply an ordered list of nodes to execute.
ExecutionPlan = List[Node]

class Solver(Protocol):
    """
    Protocol for a solver that resolves a graph into an execution plan.
    """
    def resolve(self, graph: Graph) -> ExecutionPlan:
        ...

class Executor(Protocol):
    """
    Protocol for an executor that runs a single task.
    """
    def execute(
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any]
    ) -> Any:
        ...
~~~~~

#### Acts 2: 实现原生求解器 (Native Solver)

使用 `graphlib.TopologicalSorter` 来实现一个简单、高效的求解器。

~~~~~act
write_file
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

#### Acts 3: 实现本地执行器 (Local Executor)

这个执行器负责在当前进程中同步调用任务函数。

~~~~~act
write_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
from typing import Any, Dict, List
from cascade.graph.model import Graph, Node

class LocalExecutor:
    """
    An executor that runs tasks sequentially in the current process.
    """
    def execute(
        self, 
        node: Node, 
        graph: Graph, 
        upstream_results: Dict[str, Any]
    ) -> Any:
        """
        Executes a single node's callable object by reconstructing its arguments
        from the results of its dependencies.
        """
        # Find all edges that point to the current node
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # Prepare arguments
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}
        
        # This is a simplified approach assuming we know the number of positional args
        # A more robust solution might inspect the function signature.
        # For now, we assume args are sorted by their integer `arg_name`.
        
        positional_args = {}
        
        for edge in incoming_edges:
            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                # It's a positional argument, store with its index
                positional_args[int(edge.arg_name)] = result
            else:
                # It's a keyword argument
                kwargs[edge.arg_name] = result

        # Sort and create the final positional args list
        if positional_args:
            sorted_indices = sorted(positional_args.keys())
            args = [positional_args[i] for i in sorted_indices]

        # Execute the function
        return node.callable_obj(*args, **kwargs)
~~~~~

#### Acts 4: 编写测试

创建 `tests/test_adapters.py` 来验证 `Solver` 和 `Executor` 的正确性。

~~~~~act
write_file
tests/test_adapters.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node, Graph, Edge

def test_native_solver_diamond_graph():
    @task
    def t_a(): return 1
    @task
    def t_b(x): return x + 1
    @task
    def t_c(x): return x * 2
    @task
    def t_d(y, z): return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

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

def test_local_executor():
    def add(x: int, y: int) -> int:
        return x + y
    
    # Manually construct graph for clarity
    node_x = Node(id="x", name="provide_x", callable_obj=lambda: 5)
    node_y = Node(id="y", name="provide_y", callable_obj=lambda: 10)
    node_add = Node(id="add", name="add", callable_obj=add)
    
    edge1 = Edge(source=node_x, target=node_add, arg_name="0") # positional x
    edge2 = Edge(source=node_y, target=node_add, arg_name="y") # keyword y
    
    graph = Graph(nodes=[node_x, node_y, node_add], edges=[edge1, edge2])
    
    # Simulate upstream results
    upstream_results = {
        "x": 5,
        "y": 10
    }
    
    executor = LocalExecutor()
    result = executor.execute(node_add, graph, upstream_results)
    
    assert result == 15
~~~~~

### 下一步建议
我们已经拥有了将图转化为计划 (`Solver`) 和执行单个计划步骤 (`Executor`) 的能力。
下一步是第 6 步：**集成引擎与公共 API**。我们将创建一个 `Engine` 类，它会把 `GraphBuilder`、`Solver` 和 `Executor` 串联起来，并驱动整个工作流的执行，同时通过 `MessageBus` 发布事件。
