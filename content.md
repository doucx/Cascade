非常抱歉，在之前的指令中我违反了 Quipu 的 `patch_file` 协议格式（未提供 `` 和 `.new` 标记）。由于 `build.py` 的改动幅度较大且涉及签名变更，根据 `write_file` 使用策略，我将对该文件使用 `write_file` 以确保完整性和正确性。

## [WIP] feat(graph): 集成 StaticTcoAnalyzer 到 GraphBuilder (修正版)

### 摘要头
**[WIP] feat(graph): 集成 StaticTcoAnalyzer 到 GraphBuilder**

### 错误分析
在上一轮操作中，我在 `patch_file` 指令中错误地省略了 `` 和 `.new` 参数块，导致解析器报错。这违反了 D3 公理级约束。

### 用户需求
将静态 TCO 分析器集成到图构建过程中，以便在可视化时展示潜在的跳转路径。

### 目标
1.  更新 `GraphBuilder` 逻辑，支持 AST 扫描并在发现潜在跳转时创建 `POTENTIAL` 边。
2.  更新 `visualize` 模块，为 `POTENTIAL` 边定义虚线样式。
3.  通过单元测试验证。

### 标签
#intent/build #flow/ready #priority/high #comp/graph #concept/ast #task/domain/core #task/object/graph-builder #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 重写 GraphBuilder 以支持 TCO 扫描

我们通过 `write_file` 替换 `packages/cascade-graph/src/cascade/graph/build.py` 的完整内容。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import analyze_task_source


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, scan_for_tco: bool = True) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # 1. Capture the structure of inputs
        literal_inputs = {str(i): v for i, v in enumerate(result.args)}
        literal_inputs.update(result.kwargs)

        # Pre-compute signature
        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=literal_inputs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        # 3. Handle conditionals
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        # 4. Handle dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name,
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        # 5. Handle explicit sequence dependencies
        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            potential_targets = analyze_task_source(result.task.func)
            for target_task in potential_targets:
                potential_uuid = f"potential:{result._uuid}:{target_task.name}"
                
                shadow_lr = LazyResult(
                    task=target_task,
                    args=(),
                    kwargs={},
                    _uuid=potential_uuid
                )
                
                # Visit the shadow node, disable further TCO scanning to avoid infinite recursion
                target_node = self._visit(shadow_lr, scan_for_tco=False)
                
                edge = Edge(
                    source=node,
                    target=target_node,
                    arg_name="<potential>",
                    edge_type=EdgeType.POTENTIAL
                )
                self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            literal_inputs=result.mapping_kwargs,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj)
            edge = Edge(
                source=source_node,
                target=target_node,
                arg_name=path or "dependency",
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

        elif isinstance(obj, Router):
            selector_node = self._visit(obj.selector)
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=f"{path}.selector" if path else "selector",
                router=obj,
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

            for route_key, route_result in obj.routes.items():
                route_node = self._visit(route_result)
                imp_edge = Edge(
                    source=route_node,
                    target=target_node,
                    arg_name=f"{path}.route[{route_key}]",
                    edge_type=EdgeType.ROUTER_ROUTE,
                )
                self.graph.add_edge(imp_edge)

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(
                    target_node, item, path=f"{path}[{i}]" if path else str(i)
                )

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(
                    target_node, v, path=f"{path}.{k}" if path else str(k)
                )


def build_graph(target: LazyResult) -> Graph:
    return GraphBuilder().build(target)
~~~~~

#### Acts 2: 修正可视化逻辑（POTENTIAL 边渲染）

现在使用正确的 `patch_file` 格式更新 `packages/cascade-sdk/src/cascade/tools/visualize.py`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        else:
            style = f' [label="{edge.arg_name}"]'
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        elif edge.edge_type == EdgeType.POTENTIAL:
            style = ' [style=dashed, color=red, arrowhead=open, label="potential"]'
        else:
            style = f' [label="{edge.arg_name}"]'
~~~~~

#### Acts 3: 编写集成测试

验证 `build_graph` 是否能生成包含 `POTENTIAL` 边的图。

~~~~~act
write_file
tests/engine/graph/test_build_tco.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph
from cascade.graph.model import EdgeType

@task
def leaf_task():
    return "leaf"

@task
def orchestrator(x: int):
    if x > 0:
        return leaf_task()
    return "done"

def test_build_graph_with_potential_tco():
    """
    Test that the graph builder detects the potential TCO call from
    orchestrator to leaf_task and creates a POTENTIAL edge.
    """
    workflow = orchestrator(10)
    graph = build_graph(workflow)
    
    node_names = {n.name for n in graph.nodes}
    assert "orchestrator" in node_names
    assert "leaf_task" in node_names
    
    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]
    
    assert len(potential_edges) == 1
    edge = potential_edges[0]
    assert edge.source.name == "orchestrator"
    assert edge.target.name == "leaf_task"
    assert edge.arg_name == "<potential>"

def test_build_graph_no_recursive_shadow_analysis():
    """
    Ensure that we don't infinitely analyze shadow nodes.
    """
    @task
    def task_c():
        return "C"

    @task
    def task_b():
        return task_c()

    @task
    def task_a():
        return task_b()

    workflow = task_a()
    graph = build_graph(workflow)

    node_names = {n.name for n in graph.nodes}
    assert "task_a" in node_names
    assert "task_b" in node_names
    
    # task_c should NOT be in the graph because we stop scanning at task_b
    assert "task_c" not in node_names

    potential_edges = [e for e in graph.edges if e.edge_type == EdgeType.POTENTIAL]
    assert len(potential_edges) == 1
    assert potential_edges[0].source.name == "task_a"
    assert potential_edges[0].target.name == "task_b"
~~~~~

### 下一步建议
基础设施现已就绪。建议运行这些测试，并可以尝试运行一个包含循环 TCO 的示例，通过 `visualize()` 生成 DOT 代码并查看其渲染出的虚线路径。
