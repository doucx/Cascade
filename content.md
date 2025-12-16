好的，我们继续进行测试套件的精细化重构。

在上一步中，我们建立了正确的目录结构。现在，我们将把两个职责混杂的遗留测试文件 (`test_core_adapters.py` 和 `test_core_mvp.py`) 拆分到多个职责单一的新文件中，从而彻底完成测试套件与源代码架构的对齐。

## [WIP] refactor: 拆分混杂的测试文件以实现职责单一

### 用户需求
将 `tests/adapters/test_core_adapters.py` 和 `tests/integration/test_core_mvp.py` 这两个文件中的测试用例，按照其测试目标，分别拆分并迁移到符合新架构的、职责单一的测试文件中。

### 评论
这是对测试套件重构的最后一步，也是最关键的一步。通过将测试用例原子化到与其目标代码对应的文件中，我们不仅完成了架构对齐，更重要的是，我们遵循了“高内聚、低耦合”的测试设计原则。这使得未来的测试维护工作变得极其简单和直观。

### 目标
1.  创建 `tests/adapters/solvers/test_native.py` 和 `tests/adapters/executors/test_local.py`，并从 `test_core_adapters.py` 迁移相应的测试用例。
2.  创建 `tests/spec/test_task.py`、`tests/spec/test_common.py` 和 `tests/graph/test_build.py`，并从 `test_core_mvp.py` 迁移相应的测试用例。
3.  删除迁移完成后变为空的旧测试文件。

### 基本原理
我们使用 `write_file` 操作来创建新的、职责清晰的测试文件，确保每个文件只包含与其文件名和路径相符的测试内容。完成内容迁移后，使用 `delete_file` 清理掉遗留的、已被完全拆分的旧文件，保持测试套件的整洁。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-atomicity #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: 拆分 `test_core_adapters.py`

我们将 `NativeSolver` 和 `LocalExecutor` 的测试分别放入各自的新文件中。

~~~~~act
write_file
tests/adapters/solvers/test_native.py
~~~~~
~~~~~python
from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.adapters.solvers.native import NativeSolver


def test_native_solver_diamond_graph():
    @task
    def t_a():
        return 1

    @task
    def t_b(x):
        return x + 1

    @task
    def t_c(x):
        return x * 2

    @task
    def t_d(y, z):
        return y + z

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
~~~~~
~~~~~act
write_file
tests/adapters/executors/test_local.py
~~~~~
~~~~~python
import asyncio
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node, Graph, Edge


def test_local_executor():
    def add(x: int, y: int) -> int:
        return x + y

    # Manually construct graph for clarity
    node_x = Node(id="x", name="provide_x", callable_obj=lambda: 5)
    node_y = Node(id="y", name="provide_y", callable_obj=lambda: 10)
    node_add = Node(id="add", name="add", callable_obj=add)

    edge1 = Edge(source=node_x, target=node_add, arg_name="0")  # positional x
    edge2 = Edge(source=node_y, target=node_add, arg_name="y")  # keyword y

    graph = Graph(nodes=[node_x, node_y, node_add], edges=[edge1, edge2])

    # Simulate upstream results
    upstream_results = {"x": 5, "y": 10}

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_add, graph, upstream_results, resource_context={})
    )

    assert result == 15
~~~~~
~~~~~act
delete_file
tests/adapters/test_core_adapters.py
~~~~~

#### Acts 2: 拆分 `test_core_mvp.py`

现在，我们将 `spec`（Task, Param）和 `graph`（GraphBuilder）相关的测试分离到各自对应的领域目录中。

~~~~~act
write_file
tests/spec/test_task.py
~~~~~
~~~~~python
from cascade.spec.task import task, LazyResult


def test_task_decorator_and_lazy_result():
    @task
    def add(a, b):
        return a + b

    result = add(1, 2)
    assert isinstance(result, LazyResult)
    assert result.task.name == "add"
    assert result.args == (1, 2)
    assert result.kwargs == {}
~~~~~
~~~~~act
write_file
tests/spec/test_common.py
~~~~~
~~~~~python
from cascade.spec.common import Param


def test_param_placeholder():
    p = Param("env", default="dev")
    assert p.name == "env"
    assert p.default == "dev"
~~~~~
~~~~~act
write_file
tests/graph/test_build.py
~~~~~
~~~~~python
from cascade.spec.task import task
from cascade.graph.build import build_graph


def test_build_linear_graph():
    @task
    def t1():
        return 1

    @task
    def t2(x):
        return x + 1

    r1 = t1()
    r2 = t2(r1)

    graph = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert edge.source.name == "t1"
    assert edge.target.name == "t2"
    assert edge.arg_name == "0"  # first positional arg


def test_build_diamond_graph():
    """
       A
      / \
     B   C
      \ /
       D
    """

    @task
    def t_a():
        return 1

    @task
    def t_b(x):
        return x + 1

    @task
    def t_c(x):
        return x * 2

    @task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    graph = build_graph(r_d)

    # Should have 4 nodes (A, B, C, D)
    assert len(graph.nodes) == 4

    # Should have 4 edges: A->B, A->C, B->D, C->D
    assert len(graph.edges) == 4

    # Verify A is reused (A->B and A->C)
    node_a = next(n for n in graph.nodes if n.name == "t_a")
    edges_from_a = [e for e in graph.edges if e.source == node_a]
    assert len(edges_from_a) == 2
~~~~~
~~~~~act
delete_file
tests/integration/test_core_mvp.py
~~~~~

### 下一步建议
我们已经出色地完成了对测试套件的全面重构。现在，测试套件的结构清晰、职责单一，与源代码架构完全对齐。

接下来，我建议我们回到之前发现的代码审查问题上，解决那些在 `src/` 目录中发现的代码冗余和逻辑缺陷。首先，我们可以从清理 `src/cascade/providers/http.py` 中的冗余代码开始。
