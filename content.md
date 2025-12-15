实现动态路由 (`Router`) 功能。这将允许任务的输入参数根据运行时的值动态地从多个上游任务中选择。

请注意，本阶段实现的 `Router` 仅负责**值的选择**。它不会自动对未选中的分支进行剪枝（即所有备选上游都会被执行，除非用户显式使用了 `.run_if`）。这是一个设计选择，旨在保持实现的原子性和简单性。

## [WIP] feat(core): Implement dynamic routing with `cs.Router`

### 用户需求
引入 `cs.Router` 类，使用户能够定义参数值的动态来源。系统应根据 `selector`（一个任务或参数）的运行时结果，从 `routes` 字典中选择对应的任务结果作为输入。

### 评论
这是增强 Cascade 表达能力的重要一步。通过引入 `Router`，我们将图的连接关系从静态的 1:1 绑定扩展到了动态的 1:N 选择。虽然目前不包含自动剪枝，但这已经能够支持多环境配置切换、A/B 测试数据源选择等常见场景。

### 目标
1.  创建 `src/cascade/spec/routing.py` 定义 `Router` 类。
2.  修改 `src/cascade/graph/model.py`，在 `Edge` 中添加 `router` 字段。
3.  更新 `src/cascade/graph/build.py` 以支持构建路由依赖。
4.  更新 `LocalExecutor` 以处理路由逻辑。
5.  添加测试 `tests/test_routing.py`。

### 基本原理
我们在图结构层面引入一个新的概念：**路由边**。
当一个参数的值是 `Router` 时，我们创建一条从 `selector` 到目标节点的边，并将 `Router` 对象本身附加到这条边上。同时，为了保证拓扑排序正确，我们还需要建立从所有备选 `routes` 到目标节点的隐式依赖边。
在执行时，Executor 识别出路由边，先获取 `selector` 的值，再用该值去查找并注入真正的数据结果。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/routing #scope/core #ai/instruct #task/domain/core #task/object/router #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 `Router` 规范

创建路由规范文件。

~~~~~act
write_file
src/cascade/spec/routing.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .task import LazyResult

T = TypeVar("T")

@dataclass
class Router:
    """
    A dynamic input selector.
    
    It allows a task's argument to be selected at runtime from multiple
    upstream sources based on a selector value.
    """
    selector: LazyResult[Any]
    routes: Dict[Any, LazyResult[T]]
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
from .spec.file import File
from .spec.resource import resource, inject
~~~~~
~~~~~python
from .spec.task import task, Param, LazyResult
from .spec.routing import Router
from .spec.file import File
from .spec.resource import resource, inject
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
    "run",
    "dry_run",
    "LazyResult",
    "File",
    "resource",
~~~~~
~~~~~python
    "run",
    "dry_run",
    "LazyResult",
    "Router",
    "File",
    "resource",
~~~~~

#### Acts 2: 更新图模型 (`Edge`)

在 Edge 中添加 `router` 字段以存储元数据。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""

    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str
~~~~~
~~~~~python
@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""

    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str
    # If set, implies this edge is the selector for a dynamic router
    router: Optional[Any] = None
~~~~~

#### Acts 3: 更新图构建器 (`GraphBuilder`)

处理 `Router` 对象，建立必要的边。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult
from cascade.spec.routing import Router
~~~~~

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
            if isinstance(value, LazyResult):
                # Found a dependency! Recurse.
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            else:
                # It's a literal value, store it in the node.
                target_node.literal_inputs[arg_name] = value
~~~~~
~~~~~python
            if isinstance(value, LazyResult):
                # Found a dependency! Recurse.
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                # Handle Dynamic Router
                # 1. Edge for Selector (carries the Router metadata)
                selector_node = self._visit(value.selector)
                edge = Edge(
                    source=selector_node, 
                    target=target_node, 
                    arg_name=arg_name,
                    router=value
                )
                self.graph.add_edge(edge)
                
                # 2. Edges for all possible Routes (implicit dependencies)
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    # We use a special prefix to denote implicit dependencies that
                    # shouldn't be directly injected as args, but ensure execution order.
                    # LocalExecutor will ignore these.
                    imp_edge = Edge(
                        source=route_node, 
                        target=target_node, 
                        arg_name="_implicit_dependency"
                    )
                    self.graph.add_edge(imp_edge)
            else:
                # It's a literal value, store it in the node.
                target_node.literal_inputs[arg_name] = value
~~~~~

#### Acts 4: 更新 Executor (`LocalExecutor`)

在执行时解析路由逻辑。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
        for edge in incoming_edges:
            # Skip control flow edges
            if edge.arg_name == "_condition":
                continue

            result = upstream_results[edge.source.id]
            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result
~~~~~
~~~~~python
        for edge in incoming_edges:
            # Skip control flow edges
            if edge.arg_name == "_condition":
                continue
            
            # Skip implicit dependencies (used for routing/ordering only)
            if edge.arg_name == "_implicit_dependency":
                continue

            result = upstream_results[edge.source.id]
            
            # Handle Dynamic Routing
            if edge.router:
                # 'result' is the value of the selector (e.g., "csv")
                selector_value = result
                try:
                    selected_lazy_result = edge.router.routes[selector_value]
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_value}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )
                
                # Retrieve the actual result of the selected task
                actual_value = upstream_results[selected_lazy_result._uuid]
                
                if edge.arg_name.isdigit():
                    positional_args[int(edge.arg_name)] = actual_value
                else:
                    final_kwargs[edge.arg_name] = actual_value
            else:
                # Standard dependency
                if edge.arg_name.isdigit():
                    positional_args[int(edge.arg_name)] = result
                else:
                    final_kwargs[edge.arg_name] = result
~~~~~

#### Acts 5: 添加测试

验证路由选择逻辑。

~~~~~act
write_file
tests/test_routing.py
~~~~~
~~~~~python
import pytest
import cascade as cs

def test_router_selects_correct_path():
    @cs.task
    def get_source():
        return "a"

    @cs.task
    def task_a():
        return "Result A"

    @cs.task
    def task_b():
        return "Result B"

    @cs.task
    def process(data):
        return f"Processed: {data}"

    # Router depends on get_source
    router = cs.Router(
        selector=get_source(),
        routes={
            "a": task_a(),
            "b": task_b()
        }
    )

    final = process(data=router)

    result = cs.run(final)
    assert result == "Processed: Result A"

def test_router_with_params():
    # Use Param as selector
    mode = cs.Param("mode")
    
    @cs.task
    def prod_task(): return "PROD"
    
    @cs.task
    def dev_task(): return "DEV"
    
    @cs.task
    def deploy(env_name):
        return f"Deploying to {env_name}"
        
    router = cs.Router(
        selector=mode,
        routes={
            "production": prod_task(),
            "development": dev_task()
        }
    )
    
    flow = deploy(env_name=router)
    
    # Test case 1: Development
    res_dev = cs.run(flow, params={"mode": "development"})
    assert res_dev == "Deploying to DEV"
    
    # Test case 2: Production
    res_prod = cs.run(flow, params={"mode": "production"})
    assert res_prod == "Deploying to PROD"

def test_router_invalid_selection():
    selector = cs.Param("sel")
    
    @cs.task
    def t1(): return 1
    
    router = cs.Router(selector=selector, routes={"a": t1()})
    
    @cs.task
    def consumer(x): return x
    
    with pytest.raises(ValueError, match="no matching route found"):
        cs.run(consumer(router), params={"sel": "invalid_key"})
~~~~~

### 下一步建议
实现完 `Router` 后，下一步是完成执行计划中的最后一个特性：**任务映射 (`.map`)**。这将使 Cascade 具备处理列表数据的能力。
