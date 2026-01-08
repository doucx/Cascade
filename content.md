## [WIP] 针对性分析与修复策略

# 错误分析与修复方案

当前的测试失败揭示了 "Graph-Strangler" 计划在实现细节上的几个关键漏洞。以下是针对性分析与修复策略：

## 1. 核心崩溃：`_get_param_value` 类型错误
*   **现象**: `TypeError: ... missing 1 required positional argument: 'params_context'`。
*   **原因**: `ArgumentResolver` 依赖 `if callable_obj is _get_param_value.func` 来判断是否注入参数上下文。但新的 `IRGenerator` 注册的是解包后的函数引用，虽然理论上应该是同一个对象，但在复杂的导入或包装场景下（特别是 `reflection.tasks` 中的装饰器），引用一致性检查变得脆弱。且旧逻辑未能正确识别 `ParamNode`。
*   **修复**: 修改 `ArgumentResolver`，不再依赖函数对象一致性，而是直接检查 `node.node_type == "param"` 或 `isinstance(node, ParamNode)`。这是语义上更正确的做法。

## 2. 路由崩溃：`KeyError` (Hash vs UUID)
*   **现象**: `KeyError: <physical_hash>`。
*   **原因**: `FlowManager` 使用物理 Hash（来自 Router 逻辑）去 `instance_map` 查找节点。但 `IRToRuntimeAdapter` 仅将逻辑 UUID 放入了 `instance_map`。
*   **修复**: 在 `IRToRuntimeAdapter` 中，将物理 Hash 也作为键加入 `instance_map`，使其支持双重索引。

## 3. 依赖注入失效：`AttributeError: 'Inject' object...`
*   **现象**: `conn` 参数接收到的是 `Inject` 对象本身，而不是数据库连接。
*   **原因**: `IRToRuntimeAdapter` 创建 `TaskNode` 时，默认设为 `has_complex_inputs=False`。这导致 `ArgumentResolver` 走了“快速通道”，直接传递字面量，跳过了 `Inject` 对象的解析。
*   **修复**: 在 `IRToRuntimeAdapter` 中实现扫描逻辑，如果输入中包含 `Inject` 对象，强制将 `has_complex_inputs` 设为 `True`。

## 4. 递归死锁：`Explicit Jump Loop`
*   **现象**: `RecursionError`。
*   **原因**: `IRGenerator` 在处理 `JumpSelector` 时尝试递归访问跳转目标以获取其物理 ID。如果跳转目标是自身或祖先（循环），这会导致无限递归。
*   **修复**: 修改 `IRGenerator`，对于控制流（Jump），不再强求解析物理 ID，而是使用逻辑 UUID。同时更新 `IRToRuntimeAdapter` 以支持解析这些逻辑 UUID。

## 5. 缓存失效：`File Existence Cache`
*   **现象**: 缓存命中失败。
*   **原因**: `IRToRuntimeAdapter` 忘记了从 `NodeIR` 恢复 `cache_policy`。
*   **修复**: 在 `_create_node` 中添加 `cache_policy` 的恢复逻辑。

---

## 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #comp/compiler #scope/core #ai/refine #task/domain/core #task/object/graph-execution #task/action/fix-regressions #task/state/continue

---

### Script

#### Acts 1: 修复 ArgumentResolver (针对 ParamNode)

我们将修改 `ArgumentResolver`，使其通过节点类型而非函数一致性来判断是否注入 `params_context`。同时，为了安全起见，我们增加 `ParamNode` 的导入。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/resolvers.py
~~~~~
~~~~~python.old
from cascade.graph.model import Node, Graph, Edge, EdgeType
from cascade.spec.dsl.resources import Inject
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.runtime.errors import DependencyMissingError, ResourceNotFoundError
from cascade.spec.runtime.interfaces import StateBackend

import inspect


class ArgumentResolver:
~~~~~
~~~~~python.new
from cascade.graph.model import Node, Graph, Edge, EdgeType, ParamNode
from cascade.spec.dsl.resources import Inject
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.runtime.errors import DependencyMissingError, ResourceNotFoundError
from cascade.spec.runtime.interfaces import StateBackend

import inspect


class ArgumentResolver:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/resolvers.py
~~~~~
~~~~~python.old
        # 4. Handle internal param fetching context
        # [CRITICAL] This logic must always run for Param tasks
        from cascade.reflection import _get_param_value

        if callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}

        return args, kwargs
~~~~~
~~~~~python.new
        # 4. Handle internal param fetching context
        # [CRITICAL] This logic must always run for Param tasks.
        # We check the node type explicitly, which is more robust than checking function identity
        # especially when the executable comes from different import paths or adapters.
        if isinstance(node, ParamNode):
            kwargs["params_context"] = user_params or {}

        return args, kwargs
~~~~~

#### Acts 2: 修复 IRToRuntimeAdapter (Inject, Cache, InstanceMap)

我们需要在 Adapter 中做三件事：
1.  恢复 `cache_policy`。
2.  检测 `Inject` 并设置 `has_complex_inputs`。
3.  更新 `instance_map` 以支持物理 ID 查找。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
        instance_map: Dict[str, Node] = {}
        for node_ir in ir.nodes:
            if node_ir.logical_id:
                instance_map[node_ir.logical_id] = self.node_map[
                    node_ir.current_node_instance_hash
                ]

        return self.graph, instance_map, executables
~~~~~
~~~~~python.new
        instance_map: Dict[str, Node] = {}
        for node_ir in ir.nodes:
            runtime_node = self.node_map[node_ir.current_node_instance_hash]
            
            # 1. Map Physical Hash -> Node (Used by FlowManager/Routers)
            instance_map[node_ir.current_node_instance_hash] = runtime_node
            
            # 2. Map Logical UUID -> Node (Used by External API / Legacy lookups)
            if node_ir.logical_id:
                instance_map[node_ir.logical_id] = runtime_node

        return self.graph, instance_map, executables
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
    def _create_node(self, node_ir: NodeIR) -> Node:
        # Recover policies
        retry_policy = None
        if node_ir.retry_policy:
            retry_policy = RetryPolicy(
                max_attempts=node_ir.retry_policy["max_attempts"],
                delay=node_ir.retry_policy["delay"],
                backoff=node_ir.retry_policy["backoff"],
            )

        constraints = None
~~~~~
~~~~~python.new
    def _create_node(self, node_ir: NodeIR) -> Node:
        # Recover policies
        retry_policy = None
        if node_ir.retry_policy:
            retry_policy = RetryPolicy(
                max_attempts=node_ir.retry_policy["max_attempts"],
                delay=node_ir.retry_policy["delay"],
                backoff=node_ir.retry_policy["backoff"],
            )

        # Recover Cache Policy
        # Note: IR currently doesn't strictly specify the format of cache_policy dict/object
        # But we assume the IRGenerator passes it through if attached.
        # Since IRGenerator currently copies attributes, check if it's there.
        # If node_ir.cache_policy is missing from NodeIR definition, we might need to add it or it's in inputs?
        # NodeIR def has retry_policy but missing explicit cache_policy field? 
        # Checking cascade/spec/ir/graph.py... NodeIR definition HAS retry_policy but NO cache_policy field.
        # Wait, let's check if we can pass it via metadata or if we need to extend NodeIR.
        # For this fix, let's assume we can retrieve it if we extended NodeIR or patched IRGenerator.
        # But wait, IRGenerator code:
        # node_ir = NodeIR(..., retry_policy=self._extract_retry_policy(lr))
        # It ignores cache_policy! 
        # We need to fix IRGenerator first to include cache_policy, OR pass it differently.
        # Given we are in the Adapter, let's assume we will fix IRGenerator to pass it.
        # Let's verify NodeIR structure in next step. For now, placeholder.
        cache_policy = getattr(node_ir, "cache_policy", None)

        constraints = None
~~~~~

**修正**: 我意识到 `NodeIR` 定义中可能缺少 `cache_policy` 字段，且 `IRGenerator` 没有处理它。我们需要先修改 `cascade-spec` 的 `NodeIR` 和 `cascade-compiler` 的 `IRGenerator`。

#### Acts 3: 扩展 NodeIR 并修复 IRGenerator (Cache & Recursion)

1.  向 `NodeIR` 添加 `cache_policy`。
2.  更新 `IRGenerator` 以填充 `cache_policy`。
3.  更新 `IRGenerator` 以处理循环递归问题：对于 `flow_control`，只使用逻辑 ID。
4.  在 `IRGenerator` 中处理 `Inject` 对象检测，以便 Adapter 可以使用它，或者在 Adapter 中自行检测。Adapter 检测更安全。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
    # Format: {"target_key": "target_node_id", ...}
    flow_control: Optional[Dict[str, Any]] = None

    # Metadata for retry policies, caching, etc.
    retry_policy: Optional[Dict[str, Any]] = None
~~~~~
~~~~~python.new
    # Format: {"target_key": "target_node_id", ...}
    flow_control: Optional[Dict[str, Any]] = None

    # Metadata for retry policies, caching, etc.
    retry_policy: Optional[Dict[str, Any]] = None
    cache_policy: Optional[Any] = None
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
        )

        # 5. Register
        self.nodes[node_id] = node_ir
~~~~~
~~~~~python.new
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
            cache_policy=lr._cache_policy,
        )

        # 5. Register
        self.nodes[node_id] = node_ir
~~~~~

现在解决递归问题。我们将修改 `_visit_lazy_result`，在处理 `flow_control` 时不再递归调用 `_visit`，而是直接提取 `_uuid`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        flow_control = None
        if lr._jump_selector and isinstance(lr._jump_selector, JumpSelector):
            flow_control = {}
            for k, target in lr._jump_selector.routes.items():
                if target:
                    flow_control[k] = self._visit(target)
                else:
                    flow_control[k] = None

        # 2. Analyze Task Definition
~~~~~
~~~~~python.new
        flow_control = None
        if lr._jump_selector and isinstance(lr._jump_selector, JumpSelector):
            flow_control = {}
            for k, target in lr._jump_selector.routes.items():
                if target:
                    # [Cycle Breaking]
                    # For flow control, we use the Logical ID (UUID) instead of the Physical ID
                    # to avoid infinite recursion when a Jump points back to an ancestor or self.
                    # The Runtime Adapter will use the instance_map to resolve this UUID to the Node.
                    # We DO NOT call self._visit(target) here.
                    flow_control[k] = target._uuid
                else:
                    flow_control[k] = None

        # 2. Analyze Task Definition
~~~~~

#### Acts 4: 完成 Adapter 修复 (Cache, Inject, FlowControl)

现在回到 Adapter，完成 `cache_policy` 的赋值，添加 `Inject` 检测，并处理 `flow_control` 中现在的逻辑 UUID。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
        # Input bindings: filter out router definitions from inputs
        input_bindings = {}
        for k, v in node_ir.inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue
            input_bindings[k] = v

        # Determine Node Type
        if node_ir.type == "map":
            node = MapNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="map",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
            )
        elif node_ir.type == "param":
            node = ParamNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="param",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=True,
            )
        else:
            # Check for complex inputs (heuristic)
            # In new IR, we might want an explicit flag. For now, assume False unless proven otherwise?
            # Or safe default True? GraphBuilder logic was complex.
            # Let's assume False for standard tasks unless we see specialized inputs.
            # Actually, Runtime ArgumentResolver handles complex inputs fine even if flag is False,
            # it just skips the "Fast Path". Setting False is safe but maybe slower.
            # Setting True forces complex path.
            # Let's check bindings for nested structures.
            node = TaskNode(
                current_node_instance_hash=node_ir.current_node_instance_hash,
                definition=node_ir.task,
                node_type="task",
                retry_policy=retry_policy,
                constraints=constraints,
                input_bindings=input_bindings,
                has_complex_inputs=False,  # TODO: Optimization: detect complexity
            )

        return node
~~~~~
~~~~~python.new
        # Input bindings: filter out router definitions from inputs
        input_bindings = {}
        has_complex_inputs = False
        from cascade.spec.dsl.resources import Inject
        
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
            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True

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
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
    def _reconstruct_jump_edges(self, flow_control: Dict[str, Any], source_node: Node):
        # Flow control in IR: {"target_key": "target_node_id"}
        # Runtime expects EdgeType.ITERATIVE_JUMP from Source -> Target
        # carrying a JumpSelector object.

        routes_stubs = {
            k: (_StubLazyResult(v) if v else None) for k, v in flow_control.items()
        }
        selector_obj = JumpSelector(routes=routes_stubs)  # type: ignore

        # Add edges for each potential jump target
        for key, target_id in flow_control.items():
            if target_id and target_id in self.node_map:
                target_node = self.node_map[target_id]
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
~~~~~python.new
    def _reconstruct_jump_edges(self, flow_control: Dict[str, Any], source_node: Node):
        # Flow control in IR: {"target_key": "target_logical_id"}
        # Note: Compiler now emits Logical IDs to avoid recursion cycles.
        # We need to resolve these Logical IDs to Runtime Nodes using logical_map or instance_map
        # But wait, self.logical_map maps Logical ID -> Runtime Node.
        
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

### 下一步建议
运行测试。
`uv run pytest packages/cascade-runtime/tests packages/cascade-library/tests packages/cascade-sdk/tests packages/cascade-spec/tests`
