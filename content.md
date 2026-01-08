遵循 ADAP v1.0 协议，在进行文件系统变更前进行自我审问：
1. **契约假设**: 无。删除操作是基于明确的目录结构。
2. **状态假设**: 无。
3. **数据流假设**: 无。
4. **身份假设**: 无。

我将执行“删除 cascade-graph”相关的操作。

简要回答：
计划包括删除 `cascade-graph` 包，更新 `pyproject.toml` 依赖，并修复因 Adapter 行为变更和测试代码过时导致的测试失败。

## [WIP] fix: 删除 cascade-graph 并修复 Adapter 与测试

### 用户需求
1.  物理删除 `packages/cascade-graph`。
2.  从 `pyproject.toml` 和其他包中移除对 `cascade-graph` 的依赖。
3.  修复 `cascade-runtime` 和 `cascade-application` 中因底层图构建逻辑变更导致的测试失败。

### 评论
删除遗留包是系统演进的关键一步。Adapter 的修复需要平衡：既要支持新的基于 IR 的流（Physical Hash），又要尽可能通过旧的测试用例（保持结构正确性）。

### 目标
1.  清理项目结构，移除 `cascade-graph`。
2.  优化 `IRToRuntimeAdapter`：
    *   避免将已转化为 Edge 的依赖留在 `input_bindings` 中。
    *   递归扫描 inputs 以发现嵌套的依赖并建立 Edge（满足 Legacy 测试对图结构的断言）。
3.  修正 `test_serialize.py` 中的导入错误和 ID 断言逻辑。

### 基本原理
1.  **Cleanup**: 直接 `rm -rf` 和修改 `toml`。
2.  **Adapter Fix 1 (Bindings)**: 在 `_create_node` 时，我们遍历 `inputs`。为了避免双重包含（既在 Edge 又在 Bindings），我们需要在生成 `input_bindings` 时过滤掉那些将在 `_create_edges` 中处理为 Edge 的项。这需要对“什么是 Edge”有一个统一的判断逻辑。
3.  **Adapter Fix 2 (Nested Edges)**: `test_build_graph_with_nested_dependencies` 期望即使依赖在列表中，也能在 Graph 中看到 Edge。虽然 Runtime 可能无法自动注入数据到列表内部，但 Graph 结构应该反映这种依赖关系。通过递归扫描 `inputs` 并检查值是否为 `node_map` 中的 Key 来实现。
4.  **Test Fixes**: 更新测试以适应新的包结构和 ID 机制。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #comp/runtime #scope/core #ai/instruct #task/domain/cleanup #task/object/cascade-graph #task/action/remove #task/state/continue

---

### Script

#### Acts 1: 删除 cascade-graph 包

~~~~~act
delete_file
packages/cascade-graph
~~~~~

#### Acts 2: 更新根 pyproject.toml

移除 workspace member `cascade-graph` 和依赖。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
    "cascade-spec",
    "cascade-runtime",
    "cascade-sdk",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]

[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-runtime",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-vm",
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
]
~~~~~
~~~~~new
    "cascade-spec",
    "cascade-runtime",
    "cascade-sdk",
    "cascade-library",
    "cascade-vm",
    "cascade-compiler",
]

[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-sdk = { workspace = true }
cascade-reflection = { workspace = true }
cascade-library = { workspace = true }
cascade-application = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }
cascade-connector-local = { workspace = true }
cascade-common = { workspace = true }
cascade-test-utils = { workspace = true }
cascade-vm = { workspace = true }
cascade-compiler = { workspace = true }
cascade-std = { workspace = true }
cascade = { workspace = true }
cascade-vm-rs = { workspace = true }

[tool.hatch.workspaces]
packages = [
    "packages/cascade-spec",
    "packages/cascade-runtime",
    "packages/cascade-sdk",
    "packages/cascade-provider-ipfs",
    "packages/cascade-library",
    "packages/cascade-connector-local",
    "packages/cascade-vm",
    "packages/cascade-compiler",
    "packages/cascade-std",
    "packages/cascade-vm-rs",
    "packages/cascade-reflection",
    "packages/cascade-test-utils",
]
~~~~~

#### Acts 3: 更新 cascade-compiler/pyproject.toml

`cascade-compiler` 的 `uv.sources` 引用了 `cascade-graph`，需要移除。

~~~~~act
patch_file
packages/cascade-compiler/pyproject.toml
~~~~~
~~~~~old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-graph = { workspace = true }
~~~~~
~~~~~new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~

#### Acts 4: 修复 IRToRuntimeAdapter

我们需要修改 `adapter.py` 以：
1.  在 `input_bindings` 中过滤掉那些会被转换为 Edge 的输入。
2.  递归扫描 `inputs` 以支持嵌套依赖的 Edge 创建。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, Tuple, Callable, List
from dataclasses import dataclass

from cascade.spec.ir.graph import NodeIR
from cascade.compiler.frontend.generator import GenerationResult
from cascade.runtime.graph.model import (
    Graph,
    Node,
    TaskNode,
    MapNode,
    ParamNode,
    Edge,
    EdgeType,
)
from cascade.runtime.graph.registry import NodeRegistry
from cascade.spec.dsl.fluent import RetryPolicy
from cascade.spec.dsl.constraint import ResourceConstraint
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.jump import JumpSelector


@dataclass
class _StubLazyResult:
    _uuid: str


class IRToRuntimeAdapter:
    def __init__(self, registry: Optional[NodeRegistry] = None):
        self.registry = registry or NodeRegistry()
        self.graph = Graph()
        # Maps node_instance_hash -> Runtime Node Object
        self.node_map: Dict[str, Node] = {}
        # Maps logical_uuid (from IR) -> Runtime Node Object (for router reconstruction)
        self.logical_map: Dict[str, Node] = {}

    def adapt(
        self, result: GenerationResult
    ) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
        ir = result.ir
        executables = result.executables

        # 1. Create Nodes
        for node_ir in ir.nodes:
            node = self._create_node(node_ir, executables)
            self.graph.add_node(node)
            self.node_map[node.current_node_instance_hash] = node
            if node_ir.logical_id:
                self.logical_map[node_ir.logical_id] = node

        # 2. Create Edges
        for node_ir in ir.nodes:
            target_node = self.node_map[node_ir.current_node_instance_hash]
            self._create_edges(node_ir, target_node)

        # 3. Create Instance Map (UUID -> Node) for FlowManager compatibility
        # Legacy runtime uses UUIDs for lookups in FlowManager
        instance_map: Dict[str, Node] = {}
        for node_ir in ir.nodes:
            runtime_node = self.node_map[node_ir.current_node_instance_hash]

            # 1. Map Physical Hash -> Node (Used by FlowManager/Routers)
            instance_map[node_ir.current_node_instance_hash] = runtime_node

            # 2. Map Logical UUID -> Node (Used by External API / Legacy lookups)
            if node_ir.logical_id:
                instance_map[node_ir.logical_id] = runtime_node

        return self.graph, instance_map, executables

    def _is_dependency(self, value: Any) -> bool:
        """Check if a value looks like a node reference (Physical ID)."""
        if isinstance(value, str) and value in self.node_map:
            return True
        return False

    def _create_node(self, node_ir: NodeIR, executables: Dict[str, Callable]) -> Node:
        # Recover policies
        retry_policy = None
        if node_ir.retry_policy:
            retry_policy = RetryPolicy(
                max_attempts=node_ir.retry_policy["max_attempts"],
                delay=node_ir.retry_policy["delay"],
                backoff=node_ir.retry_policy["backoff"],
            )

        constraints = None
        if node_ir.constraints:
            constraints = ResourceConstraint(requirements=node_ir.constraints)

        # Input bindings: filter out router definitions and dependencies
        input_bindings = {}
        has_complex_inputs = False
        from cascade.spec.dsl.resources import Inject
        import inspect

        def check_complexity(obj):
            if isinstance(obj, Inject):
                return True
            if isinstance(obj, (list, tuple)):
                return any(check_complexity(x) for x in obj)
            if isinstance(obj, dict):
                return any(check_complexity(x) for x in obj.values())
            return False

        for k, v in node_ir.inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue
            
            # If it's a direct dependency string, don't add to bindings
            if self._is_dependency(v):
                continue
                
            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True

        # Also check the executable signature for Inject defaults
        if not has_complex_inputs:
            executable = executables.get(node_ir.current_node_instance_hash)
            if executable:
                try:
                    sig = inspect.signature(executable)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            has_complex_inputs = True
                            break
                except (ValueError, TypeError):
                    pass

        # Determine Node Type
        if node_ir.type == "map":
            node = MapNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="map",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
            )
        elif node_ir.type == "param":
            node = ParamNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="param",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=True,
            )
        else:
            node = TaskNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="task",
                retry_policy=retry_policy,
                cache_policy=node_ir.cache_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex_inputs,
            )

        return node

    def _create_edges(self, node_ir: NodeIR, target_node: Node):
        # 1. Data Edges & Routers
        for arg_name, value in node_ir.inputs.items():
            if self._is_dependency(value):
                # Simple Data Dependency (Node ID ref)
                source_node = self.node_map[value]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name=arg_name,
                        edge_type=EdgeType.DATA,
                    )
                )
            elif isinstance(value, dict) and value.get("$router"):
                # Reconstruct Router
                self._reconstruct_router_edges(value, arg_name, target_node)
            else:
                # Recursively scan for nested dependencies to ensure Graph connectivity
                self._scan_and_create_nested_edges(value, arg_name, target_node)

        # 2. Condition
        if node_ir.condition and node_ir.condition in self.node_map:
            source_node = self.node_map[node_ir.condition]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )

        # 3. Sequencing Dependencies
        for dep_id in node_ir.dependencies:
            if dep_id in self.node_map:
                source_node = self.node_map[dep_id]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name="<sequence>",
                        edge_type=EdgeType.SEQUENCE,
                    )
                )

        # 4. Jump / Flow Control
        if node_ir.flow_control:
            self._reconstruct_jump_edges(node_ir.flow_control, target_node)

        # 5. Constraint Edges
        if node_ir.constraints:
            from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult

            for key, val in node_ir.constraints.items():
                if isinstance(val, (LazyResult, MappedLazyResult)):
                    if val._uuid in self.logical_map:
                        source_node = self.logical_map[val._uuid]
                        self.graph.add_edge(
                            Edge(
                                source=source_node,
                                target=target_node,
                                arg_name=key,
                                edge_type=EdgeType.CONSTRAINT,
                            )
                        )

    def _scan_and_create_nested_edges(self, obj: Any, arg_name: str, target_node: Node):
        """Recursively scan object for Node IDs and create edges."""
        if self._is_dependency(obj):
            source_node = self.node_map[obj]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name=arg_name,
                    edge_type=EdgeType.DATA,
                )
            )
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._scan_and_create_nested_edges(item, arg_name, target_node)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._scan_and_create_nested_edges(value, arg_name, target_node)

    def _reconstruct_router_edges(
        self, router_def: Dict[str, Any], arg_name: str, target_node: Node
    ):
        selector_id = router_def["selector"]
        routes_def = router_def["routes"]

        if selector_id not in self.node_map:
            return  # Error or stub?

        selector_node = self.node_map[selector_id]

        selector_stub = _StubLazyResult(selector_id)
        routes_stubs = {k: _StubLazyResult(v) for k, v in routes_def.items() if v}

        router_obj = Router(selector=selector_stub, routes=routes_stubs)  # type: ignore

        # 1. Edge from Selector -> Target (carrying Router obj)
        self.graph.add_edge(
            Edge(
                source=selector_node,
                target=target_node,
                arg_name=arg_name,
                edge_type=EdgeType.DATA,
                router=router_obj,
            )
        )

        # 2. Edges from Routes -> Target
        for key, route_node_id in routes_def.items():
            if route_node_id and route_node_id in self.node_map:
                route_node = self.node_map[route_node_id]
                self.graph.add_edge(
                    Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"{arg_name}.route[{key}]",
                        edge_type=EdgeType.ROUTER_ROUTE,
                    )
                )

    def _reconstruct_jump_edges(self, flow_control: Dict[str, Any], source_node: Node):
        routes_stubs = {
            k: (_StubLazyResult(v) if v else None) for k, v in flow_control.items()
        }
        selector_obj = JumpSelector(routes=routes_stubs)  # type: ignore

        # Add edges for each potential jump target
        for key, target_logical_id in flow_control.items():
            if target_logical_id and target_logical_id in self.logical_map:
                target_node = self.logical_map[target_logical_id]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name=key,
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector_obj,
                    )
                )
~~~~~

#### Acts 5: 修复序列化测试

修复 `AttributeError: module 'cascade' has no attribute 'graph'` 和 UUID 不匹配问题。

~~~~~act
patch_file
packages/cascade-runtime/tests/legacy_graph/unit/test_serialize.py
~~~~~
~~~~~python.old
    data_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.DATA
    ]
    condition_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONDITION
    ]
    constraint_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == cs.graph.model.EdgeType.CONSTRAINT
    ]

    assert len(data_edges) == 1
    assert len(condition_edges) == 1
    assert len(constraint_edges) == 1

    # Verify the restored types are correct
    assert condition_edges[0].edge_type is cs.graph.model.EdgeType.CONDITION
    assert constraint_edges[0].edge_type is cs.graph.model.EdgeType.CONSTRAINT
~~~~~
~~~~~python.new
    from cascade.runtime.graph.model import EdgeType

    data_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == EdgeType.DATA
    ]
    condition_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == EdgeType.CONDITION
    ]
    constraint_edges = [
        e
        for e in restored_graph.edges
        if e.target == target_node and e.edge_type == EdgeType.CONSTRAINT
    ]

    assert len(data_edges) == 1
    assert len(condition_edges) == 1
    assert len(constraint_edges) == 1

    # Verify the restored types are correct
    assert condition_edges[0].edge_type is EdgeType.CONDITION
    assert constraint_edges[0].edge_type is EdgeType.CONSTRAINT
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/tests/legacy_graph/unit/test_serialize.py
~~~~~
~~~~~python.old
    assert edge.router is not None
    # Check that the stub has the correct UUIDs
    assert edge.router.selector._uuid == selector._uuid
    assert edge.router.routes["a"]._uuid == route_a._uuid
    assert edge.router.routes["b"]._uuid == route_b._uuid
~~~~~
~~~~~python.new
    assert edge.router is not None
    # Check that the stub has the correct UUIDs (Physical Hash)
    # The restored router contains the physical node IDs as UUIDs
    assert edge.router.selector._uuid == selector_node.current_node_instance_hash
    # We need to find the route nodes in the restored graph to compare IDs
    restored_route_a = next(n for n in restored_graph.nodes if n.name == "task_a")
    restored_route_b = next(n for n in restored_graph.nodes if n.name == "task_b")
    assert edge.router.routes["a"]._uuid == restored_route_a.current_node_instance_hash
    assert edge.router.routes["b"]._uuid == restored_route_b.current_node_instance_hash
~~~~~

### 下一步建议
运行测试验证修复效果。如果测试通过，我们可以继续进行最终的收尾工作（如删除未使用的临时文件或代码）。
