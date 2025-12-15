## [WIP] feat: 初始化 Cascade MVP 核心 (骨架、模型与构建器)

### 用户需求
执行 Cascade 阶段一 (MVP) 的前三步：
1.  **项目初始化**：建立目录结构和 `pyproject.toml`。
2.  **核心模型**：定义 `Graph`, `Node`, `Edge` 以及 `Task`, `LazyResult`, `Param`。
3.  **构建逻辑**：实现从 `LazyResult` 递归构建 `Graph` 的逻辑。
4.  **测试**：编写相关测试用例。

### 评论
这是整个项目的基石。采用 `LazyResult` 树作为中间表示，并在需要时通过遍历构建 `Graph` 是一种非常干净、符合函数式编程思想的设计。它避免了全局状态，使得系统更易于测试和并行化。

### 目标
1.  创建 `cascade-py` 及其子包结构。
2.  实现零依赖的 `cascade.graph.model`。
3.  实现 `cascade.spec.task`，包括泛型的 `LazyResult` 和 `@task` 装饰器。
4.  实现 `cascade.graph.build`，能够正确处理共享依赖（菱形结构）。
5.  通过 `pytest` 验证上述组件。

### 基本原理
*   **洋葱架构**：`graph.model` 不依赖任何东西。`spec` 仅依赖 Python 标准库。`build` 依赖 `spec` 和 `model`。
*   **声明式设计**：调用 `@task` 装饰的函数不执行任何操作，仅返回描述计算意图的 `LazyResult` 对象。
*   **构建策略**：图构建器从目标节点出发，通过深度优先搜索（DFS）发现所有依赖，同时使用缓存（Memoization）确保每个逻辑节点在图中只对应一个物理 `Node` 实例。

### 标签
#intent/build #flow/ready #priority/critical
#task/domain/core #task/object/graph-engine #task/action/initialization
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 初始化项目骨架与配置

首先，我们创建项目配置 `pyproject.toml` 和基本的目录结构。

~~~~~act
write_file
pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-py"
version = "0.1.0"
description = "A modern, declarative automation library for Python."
readme = "README.md"
requires-python = ">=3.8"
license = "MIT"
authors = [
  { name = "Cascade Team", email = "dev@cascade.local" },
]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "Programming Language :: Python :: 3",
]
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-cov",
  "mypy",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p src/cascade/graph src/cascade/spec src/cascade/runtime src/cascade/adapters/executors src/cascade/adapters/solvers src/cascade/adapters/caching tests
touch src/cascade/__init__.py
touch src/cascade/graph/__init__.py
touch src/cascade/spec/__init__.py
touch src/cascade/runtime/__init__.py
touch src/cascade/adapters/__init__.py
touch src/cascade/adapters/executors/__init__.py
touch src/cascade/adapters/solvers/__init__.py
touch src/cascade/adapters/caching/__init__.py
~~~~~

#### Acts 2: 定义核心图模型 (Graph Model)

实现 `cascade.graph.model`。这是洋葱的最内核，只包含纯数据结构。

~~~~~act
write_file
src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Any, Callable

@dataclass
class Node:
    """Represents a node in the computation graph."""
    id: str
    name: str
    callable_obj: Callable
    # We might store additional metadata here later
    
    def __hash__(self):
        return hash(self.id)

@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""
    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str 

@dataclass
class Graph:
    """A container for nodes and edges representing the workflow."""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 3: 定义规格 (Specs)

实现 `cascade.spec.task`。这里定义了面向用户的 API 对象：`Task`, `LazyResult`, `Param`。

~~~~~act
write_file
src/cascade/spec/task.py
~~~~~
~~~~~python
from typing import TypeVar, Generic, Callable, Any, Dict, Optional
from dataclasses import dataclass, field
import inspect
from uuid import uuid4

T = TypeVar("T")

@dataclass
class Param:
    """Represents a runtime parameter."""
    name: str
    default: Any = None
    type: Any = None
    description: str = ""

@dataclass
class LazyResult(Generic[T]):
    """
    A placeholder for the result of a task execution.
    It holds the task that produces it and the arguments passed to that task.
    """
    task: 'Task[T]'
    args: tuple
    kwargs: Dict[str, Any]
    _uuid: str = field(default_factory=lambda: str(uuid4()))

    def __hash__(self):
        return hash(self._uuid)

class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """
    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        # Signature inspection for validation (future enhancement)
        self._signature = inspect.signature(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
        return LazyResult(task=self, args=args, kwargs=kwargs)

    def __repr__(self):
        return f"<Task {self.name}>"

def task(func: Callable[..., T]) -> Task[T]:
    """Decorator to convert a function into a Task."""
    return Task(func)
~~~~~

#### Acts 4: 实现图构建逻辑 (Graph Builder)

实现 `cascade.graph.build`。这个模块负责解析 `LazyResult` 及其依赖，构建出 `Graph` 对象。

~~~~~act
write_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Set
from uuid import uuid4
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult, Task

class GraphBuilder:
    """
    Constructs a Graph from a target LazyResult by traversing dependencies.
    """
    def __init__(self):
        self.graph = Graph()
        # Map LazyResult UUID to created Node to ensure singularity (handle diamond deps)
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, result: LazyResult) -> Node:
        # If we already processed this specific LazyResult instance, return its Node
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # Create a new Node for this task execution
        node = Node(
            id=result._uuid,
            name=result.task.name,
            callable_obj=result.task.func
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Traverse inputs (args and kwargs) to find dependencies
        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)
        
        for key, value in iterator:
            arg_name = str(key) # key is int for args, str for kwargs
            
            if isinstance(value, LazyResult):
                # Found a dependency! Recurse.
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            
            # TODO: Handle lists/dicts containing LazyResults (Future MVP enhancement)

def build_graph(target: LazyResult) -> Graph:
    """Helper function to build a graph from a result."""
    return GraphBuilder().build(target)
~~~~~

#### Acts 5: 编写测试

编写 `tests/test_core_mvp.py` 来验证骨架、模型和构建逻辑。

~~~~~act
write_file
tests/test_core_mvp.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task, LazyResult
from cascade.graph.build import build_graph
from cascade.graph.model import Graph, Node

def test_task_decorator_and_lazy_result():
    @task
    def add(a, b):
        return a + b

    result = add(1, 2)
    assert isinstance(result, LazyResult)
    assert result.task.name == "add"
    assert result.args == (1, 2)
    assert result.kwargs == {}

def test_build_linear_graph():
    @task
    def t1(): return 1
    @task
    def t2(x): return x + 1

    r1 = t1()
    r2 = t2(r1)

    graph = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    
    edge = graph.edges[0]
    assert edge.source.name == "t1"
    assert edge.target.name == "t2"
    assert edge.arg_name == "0" # first positional arg

def test_build_diamond_graph():
    """
       A
      / \
     B   C
      \ /
       D
    """
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

    # Should have 4 nodes (A, B, C, D)
    assert len(graph.nodes) == 4
    
    # Should have 4 edges: A->B, A->C, B->D, C->D
    assert len(graph.edges) == 4

    # Verify A is reused (A->B and A->C)
    node_a = next(n for n in graph.nodes if n.name == "t_a")
    edges_from_a = [e for e in graph.edges if e.source == node_a]
    assert len(edges_from_a) == 2

def test_param_placeholder():
    from cascade.spec.task import Param
    p = Param("env", default="dev")
    assert p.name == "env"
    assert p.default == "dev"
~~~~~

### 下一步建议
当前的实现已经完成了核心的数据结构和图构建。下一步是让这个图“动起来”。
建议的步骤：
1.  **实现 `Runtime` 基础**：实现 `MessageBus` 和基本的事件定义。
2.  **实现 `NativeSolver`**：使用 `graphlib` 对构建好的 `Graph` 进行拓扑排序。
3.  **实现 `LocalExecutor`**：编写执行器逻辑，使其能真正调用函数并传递数据。
