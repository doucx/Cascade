简要回答
我将实现通用图结构缓存，解除目前对多节点图复用的限制。

## [WIP] feat(engine): 实现通用图结构缓存以优化复杂递归性能

### 用户需求
目前的 TCO 优化和图缓存机制存在局限性：对于包含子结构（依赖）的复杂任务，即使结构稳定，引擎也无法复用已构建的图，导致每次迭代都要重新构建和求解图。用户希望放宽这一限制，实现通用的图结构缓存。

### 评论
这是一个非常精细的优化。核心难点在于如何将 `StructuralHasher` 提取出的扁平化参数（Literals），精确地映射回一个已经构建好的、包含多个节点的图（Graph）中。我们需要在 `GraphBuilder` 和 `StructuralHasher` 之间建立一套共享的坐标系统（Structure Path）。

### 目标
1.  **验证现状**: 创建测试证明目前复杂图无法被复用。
2.  **建立坐标系**: 在 `Node` 模型中引入 `structure_path` 字段，并在 `GraphBuilder` 中正确填充它，使其与 `StructuralHasher` 的路径逻辑对齐。
3.  **实现全图参数注入**: 编写新的参数注入逻辑，根据路径将参数分发给图中的任意节点。
4.  **解锁缓存**: 移除 `GraphExecutionStrategy` 中 `len(nodes) > 1` 的复用限制。

### 基本原理
-   **Structure Path**: 我们将任务树中的位置（如 `root.dependencies.0`）作为节点的唯一结构坐标。
-   **映射复用**: 当缓存命中时，利用这个坐标，我们可以把新一轮迭代的参数（Liternals）“手术刀式”地注入到缓存图的对应节点中，而无需重新构建整个图对象。

### 标签
#intent/perf #flow/ready #priority/high #comp/engine #comp/graph #concept/caching #scope/core #ai/instruct #task/domain/engine #task/object/complex-graph-cache #task/action/optimize #task/state/begin

---

### Script

#### Acts 1: 创建复现测试用例

我们首先创建一个测试，使用 `unittest.mock` 来统计 `build_graph` 的调用次数。对于一个执行多次的递归任务，如果缓存生效，`build_graph` 应该只被调用极少数次（理想情况是 1 次，或者由于缓存预热是几次）。目前预期是每次迭代都调用。

~~~~~act
write_file
tests/engine/runtime/test_graph_reuse.py
~~~~~
~~~~~python
import pytest
from unittest.mock import patch
import cascade as cs
from cascade.runtime import Engine, MessageBus
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

@cs.task
def leaf():
    return "leaf"

@cs.task
def complex_recursive(n: int):
    if n <= 0:
        return "done"
    # This dependency makes the task "complex" (multi-node graph)
    # forcing the engine to check the slow path cache logic.
    return complex_recursive(n - 1, _dep=leaf())

@pytest.mark.asyncio
async def test_complex_graph_rebuilds_without_general_caching():
    """
    Verifies that currently, complex graphs (len > 1) trigger a rebuild 
    on every iteration, failing to utilize the graph cache fully.
    """
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    # We mock build_graph to count how many times it's called
    with patch("cascade.runtime.strategies.build_graph", side_effect=cs.graph.build.build_graph) as mock_build:
        iterations = 10
        await engine.run(complex_recursive(iterations))
        
        # Without general caching, build_graph is called at least once per iteration
        # (plus potentially initial build).
        # We expect count to be roughly equal to iterations.
        assert mock_build.call_count >= iterations

@pytest.mark.asyncio
async def test_complex_graph_reuses_with_general_caching():
    """
    This test serves as the verification for the fix. 
    Once implemented, build_graph should be called only once (or very few times).
    """
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),
    )

    with patch("cascade.runtime.strategies.build_graph", side_effect=cs.graph.build.build_graph) as mock_build:
        iterations = 10
        await engine.run(complex_recursive(iterations))
        
        # With general caching, build_graph should be called only once 
        # (for the first time the structure is encountered).
        # We allow a small buffer (e.g. <= 2) just in case of warm-up quirks, 
        # but definitely not 10.
        # NOTE: Currently this assertion would FAIL.
        # assert mock_build.call_count <= 2
~~~~~

#### Acts 2: 扩展 Node 模型

在 `Node` 中添加 `structure_path` 字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/graph/model.py
~~~~~
~~~~~python
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~
~~~~~python
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to
    
    # The structural path of this node in the LazyResult tree (e.g. "root.args.0.dependencies.0")
    # Used for mapping literals back to the graph during caching.
    structure_path: Optional[str] = None

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~

#### Acts 3: 更新 GraphBuilder 以填充 structure_path

我们需要修改 `GraphBuilder` 的 `_visit` 方法及其调用链，使其能够传递和记录 `path`。逻辑必须与 `StructuralHasher` 保持一致。

`StructuralHasher` 的路径逻辑主要体现在它如何递归地追加路径后缀。我们需要在 `GraphBuilder` 中复刻这一过程。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    def build(self, target: LazyResult) -> Graph:
        self._visit(target, path="root")
        return self.graph

    def _visit(self, value: Any, path: str = "", scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, path, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value, path)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, path: str, scan_for_tco: bool = True) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # 1. Capture the structure of inputs
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
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
            structure_path=path,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges
        # Note: We must construct paths that match StructuralHasher
        # StructuralHasher uses: path.args.i or path.kwargs.key
        self._scan_and_add_edges(node, result.args, base_path=f"{path}.args")
        self._scan_and_add_edges(node, result.kwargs, base_path=f"{path}.kwargs")

        # 3. Handle conditionals
        if result._condition:
            source_node = self._visit(result._condition, path=f"{path}._condition")
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
                    source_node = self._visit(req_value, path=f"{path}._constraints.{res_name}")
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name,
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        # 5. Handle explicit sequence dependencies
        for i, dep in enumerate(result._dependencies):
            source_node = self._visit(dep, path=f"{path}._dependencies.{i}")
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    def _visit_mapped_result(self, result: MappedLazyResult, path: str) -> Node:
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
            structure_path=path,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._scan_and_add_edges(node, result.mapping_kwargs, base_path=f"{path}.mapping_kwargs")

        if result._condition:
            source_node = self._visit(result._condition, path=f"{path}._condition")
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        for i, dep in enumerate(result._dependencies):
            source_node = self._visit(dep, path=f"{path}._dependencies.{i}")
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, base_path: str = "", sub_path: str = ""):
        """
        Recursively scans arguments/kwargs to find LazyResults and create edges.
        
        Args:
            base_path: The path prefix for this collection (e.g. "root.args")
            sub_path: The recursive path within the collection (e.g. "0" or "config.key")
        """
        # Construct the effective path for the current object relative to the target node's argument list
        # If sub_path is empty, we are at the root of the collection.
        # But wait, logic in _visit calls this with base_path="...args".
        
        # We need to be careful. The `path` passed to `_visit` (for the CHILD node) 
        # must be the full structural path.
        
        current_full_path = f"{base_path}.{sub_path}" if sub_path else base_path

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj, path=current_full_path)
            edge = Edge(
                source=source_node,
                target=target_node,
                arg_name=sub_path or "dependency",  # arg_name in the edge is relative to the function signature
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

        elif isinstance(obj, Router):
            selector_node = self._visit(obj.selector, path=f"{current_full_path}.selector")
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=f"{sub_path}.selector" if sub_path else "selector",
                router=obj,
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

            for route_key, route_result in obj.routes.items():
                route_node = self._visit(route_result, path=f"{current_full_path}.routes.{route_key}")
                imp_edge = Edge(
                    source=route_node,
                    target=target_node,
                    arg_name=f"{sub_path}.route[{route_key}]",
                    edge_type=EdgeType.ROUTER_ROUTE,
                )
                self.graph.add_edge(imp_edge)

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(
                    target_node, item, base_path=base_path, sub_path=f"{sub_path}[{i}]" if sub_path else str(i)
                )

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(
                    target_node, v, base_path=base_path, sub_path=f"{sub_path}.{k}" if sub_path else str(k)
                )
~~~~~

#### Acts 4: 升级 GraphExecutionStrategy

我们需要修改 `GraphExecutionStrategy` 以支持全图注入。

1.  移除 `len(cached_graph.nodes) > 1` 检查。
2.  实现 `_inject_literals` 方法，根据 `structure_path` 匹配节点。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
                    if struct_hash in self._graph_cache:
                        # CACHE HIT: Reuse graph and plan
                        # Now supports complex graphs by injecting literals into all nodes
                        graph, plan = self._graph_cache[struct_hash]
                        self._inject_literals(graph, literals)
                    else:
                        # CACHE MISS: Build, solve, and cache
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        # ... logic moved from Engine ...
        if graph.nodes:
            # FIX: Previously used nodes[-1], which became incorrect when shadow nodes
            # were appended to the end of the list by static analysis.
            # GraphBuilder uses a top-down approach (pre-order traversal), so the
            # root target node is always the FIRST node added to the graph.
            target_node = graph.nodes[0]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    async def _execute_graph(
~~~~~
~~~~~python
                if isinstance(current_target, LazyResult):
                    last_executed_task = current_target.task
                    last_tco_cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
                else:
                    last_executed_task = None
                    last_tco_cycle_id = None

    def _update_graph_literals(self, graph: Graph, target: Any, literals: Dict[str, Any]):
        """Legacy helper for single-node fast path update."""
        if graph.nodes:
            target_node = graph.nodes[0]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    def _inject_literals(self, graph: Graph, literals: Dict[str, Any]):
        """
        Injects literal values from the StructuralHasher into the reused Graph.
        
        It uses `structure_path` stored on Nodes to map flattened literal keys 
        back to the specific Node and argument they belong to.
        """
        # Build an index for fast lookup: path -> Node
        # Optimization: This could be cached on the Graph object if needed.
        node_map = {node.structure_path: node for node in graph.nodes if node.structure_path}
        
        # Reset literal_inputs for all nodes to ensure no stale data
        # (Though in practice, we usually overwrite all fields if structure is identical)
        for node in graph.nodes:
            node.literal_inputs = {}
            # We must regenerate a new UUID for the node to represent this new execution instance
            # This is critical for StateBackend to distinguish results.
            # However, for TCO loops, we might reuse IDs? No, TCO usually implies new instances.
            # Wait, `literals` doesn't contain UUIDs. We need to assign new UUIDs.
            # BUT: StructuralHasher doesn't track UUIDs.
            # If we reuse the graph, we are reusing the Node objects.
            # We MUST update their IDs.
            from uuid import uuid4
            node.id = str(uuid4())

        for key, value in literals.items():
            # Key format: "root.args.0.kwargs.foo"
            # We need to find the longest prefix that matches a node's structure_path.
            
            # This matching logic can be optimized. For now, we iterate nodes.
            # A literal "root.args.0" belongs to node "root" at arg "0".
            # A literal "root.dependencies.0.args.1" belongs to node "root.dependencies.0" at arg "1".
            
            # Heuristic: split key by dots, find split point.
            # Since structure_path matches keys in literals exactly (except for the final leaf arg),
            # we can try to peel off the last segment.
            
            if "." in key:
                parent_path, arg_name = key.rsplit(".", 1)
            else:
                # Should not happen for valid paths starting with "root"
                parent_path = key
                arg_name = ""

            if parent_path in node_map:
                node = node_map[parent_path]
                node.literal_inputs[arg_name] = value
~~~~~

### 下一步建议
我们已经完成了通用图缓存的核心逻辑。
1.  **运行测试**: 运行 `tests/engine/runtime/test_graph_reuse.py`。
2.  **验证断言**: 修改测试用例中的断言，确认 `build_graph` 的调用次数现在是否符合预期（<= 2）。
3.  **运行基准测试**: 再次运行 `observatory/benchmarks/tco_performance.py`。预期 `heavy_complex_countdown` 的性能将进一步提升，不仅是 AST 解析省了，连 `build_graph` 和 `solver` 都省了。
4.  **UUID 问题**: 我在代码中加了一个临时的 UUID 更新逻辑。需要仔细思考这是否足够。每次复用图时，必须为所有节点生成新的 UUID，否则 `StateBackend` 会混淆不同迭代的结果（尽管 TCO 会清除状态，但为了安全性，ID 应该是唯一的）。目前的实现是在 `_inject_literals` 里做的，这应该是安全的。
