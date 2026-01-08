基于对架构的深入分析和绞杀计划（Operation Graph-Strangler）的阶段一要求，我将对 `cascade-spec` 和 `cascade-compiler` 进行必要的扩展，使其具备描述高级控制流（Router, Jump, Map）的能力。

以下计划包含：
1.  **Spec 升级**: 扩展 `NodeIR` 以支持节点类型、Jump 选择器和 Router 输入结构。
2.  **Compiler 升级**: 修改 `IRGenerator` 以全面支持 `LazyResult` 的所有特性，包括 `Router`, `MappedLazyResult` 和 `JumpSelector`。

## [WIP] feat(compiler): 增强 IRGenerator 以支持 Router、Jump 和 Map

### 目标
使 `cascade-compiler` 的 `IRGenerator` 具备处理所有 DSL 构造的能力，从而在功能上对齐 `cascade-graph` 的 `GraphBuilder`，为后续替换打下基础。

### 用户需求
- 系统需要一个单一的、权威的逻辑图生成器。
- `GraphIR` 必须能够无损地表达动态路由 (`Router`)、迭代跳转 (`Jump`) 和 映射任务 (`Map`)。

### 评论
目前的 `GraphIR` 过于简化，只能表达基本的 DAG。为了支持 Runtime 的全部能力，我们需要将其升级为完全体的 IR。这种升级是“无损”的，即现有的简单图仍然有效，但新的复杂图也能被表达。

### 基本原理
1.  **NodeIR 扩展**: 增加 `type` 字段区分 `task` 和 `map`。增加 `flow_control` 字段存放 Jump 逻辑。
2.  **Input 协议扩展**: 定义一种特殊的 Input 结构（`{"$router": ...}`）来在 `inputs` 字典中表达 Router，而不是修改 `NodeIR` 的结构。这样保持了 `inputs` 的通用性。
3.  **Generator 增强**: 实现对 `MappedLazyResult` 的遍历，以及对 `Router` 对象的特殊序列化处理。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #concept/ir #scope/core #ai/instruct #task/domain/compiler #task/object/ir-generator #task/action/hardening #task/state/begin

---

### Script

#### Acts 1: 扩展 GraphIR 规范

首先，我们需要升级 `NodeIR` 的定义，使其能够容纳新的元数据。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class NodeIR:
    current_node_instance_hash: str

    name: str

    task: TaskDef

    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)

    # The ID of the node that determines if this node should run
    condition: Optional[str] = None

    # IDs of nodes that must complete before this node starts (Sequence dependency)
    dependencies: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GraphIR:
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class NodeIR:
    current_node_instance_hash: str

    name: str

    task: TaskDef

    # "task" | "map" | "param"
    type: str = "task"

    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)

    # The ID of the node that determines if this node should run
    condition: Optional[str] = None

    # IDs of nodes that must complete before this node starts (Sequence dependency)
    dependencies: List[str] = field(default_factory=list)

    # Configuration for iterative jumps (if any)
    # Format: {"target_key": "target_node_id", ...}
    flow_control: Optional[Dict[str, Any]] = None

    # Metadata for retry policies, caching, etc.
    retry_policy: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GraphIR:
~~~~~

#### Acts 2: 升级 IRGenerator

现在我们更新 `IRGenerator`，使其能够生成上述扩展后的 `NodeIR`。我们将添加对 `Router`, `JumpSelector`, `MappedLazyResult` 的支持。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
from typing import Any, Dict

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.dsl.routing import Router
from cascade.spec.ir.graph import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService


class IRGenerator:
    def __init__(self):
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        # id -> NodeIR
        self.nodes: Dict[str, NodeIR] = {}
        # Tracks visited LazyResult UUIDs to their generated Node IDs to handle DAGs
        self._visited: Dict[str, str] = {}

    def generate(self, target: Any) -> GraphIR:
        # If target is a list, treat all items as roots. Otherwise, wrap it.
        targets = target if isinstance(target, (list, tuple)) else [target]
        root_logical_ids = []

        for t in targets:
            if isinstance(t, LazyResult):
                root_logical_ids.append(t._uuid)
            self._visit(t)

        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(
            nodes=list(self.nodes.values()), root_logical_ids=root_logical_ids
        )

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
        elif isinstance(obj, (MappedLazyResult, Router)):
            raise NotImplementedError(
                f"Compiler Frontend currently does not support {type(obj).__name__}."
            )
        elif isinstance(obj, (list, tuple)):
            return type(obj)(self._visit(item) for item in obj)
        elif isinstance(obj, dict):
            return {k: self._visit(v) for k, v in obj.items()}
        else:
            # Literal value
            return obj

    def _visit_lazy_result(self, lr: LazyResult) -> str:
        # If already visited, return the cached Node ID
        if lr._uuid in self._visited:
            return self._visited[lr._uuid]

        # 1. Resolve Dependencies (Post-order)
        # We visit args and kwargs first to ensure dependencies are registered.
        transformed_args = [self._visit(arg) for arg in lr.args]
        transformed_kwargs = {k: self._visit(v) for k, v in lr.kwargs.items()}

        # Handle Condition (visit it so it's registered)
        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        # Handle Explicit Dependencies (visit them)
        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        # 2. Analyze Task Definition
        task_def = self.analyzer.analyze(lr.task)

        # 3. Compute Instance Hash (Node ID)
        # We need a dictionary of dependency nodes for the hasher.
        # Since we visited children first, their NodeIRs are already in self.nodes.
        # We map UUIDs of dependencies to their NodeIR objects.
        # HashingService expects `dep_nodes` to map UUID -> Node object.
        # Here we map UUID -> NodeIR. HashingService should be compatible or adapted.
        # Let's verify HashingService adaptation:
        # It uses `getattr(node, "id", ...)` so NodeIR is compatible.
        dep_map = {}

        def collect_deps(raw_obj):
            if isinstance(raw_obj, LazyResult):
                if raw_obj._uuid in self._visited:
                    node_id = self._visited[raw_obj._uuid]
                    dep_map[raw_obj._uuid] = self.nodes[node_id]
            elif isinstance(raw_obj, (list, tuple)):
                for x in raw_obj:
                    collect_deps(x)
            elif isinstance(raw_obj, dict):
                for x in raw_obj.values():
                    collect_deps(x)

        for arg in lr.args:
            collect_deps(arg)
        for val in lr.kwargs.values():
            collect_deps(val)

        # Also collect deps for condition and dependencies for hashing
        if lr._condition:
            collect_deps(lr._condition)
        for dep in lr._dependencies:
            collect_deps(dep)

        node_id = self.hashing_service.compute_node_instance_hash(task_def, lr, dep_map)

        # 4. Construct NodeIR
        # Flatten args and kwargs into a single 'inputs' dictionary
        inputs = {}
        for i, val in enumerate(transformed_args):
            inputs[str(i)] = val
        for k, val in transformed_kwargs.items():
            inputs[k] = val

        # Handle Constraints
        constraints = {}
        if lr._constraints:
            # We currently assume constraint values are literals.
            # TODO: Handle dynamic constraints (LazyResult in constraints)
            constraints = lr._constraints.requirements.copy()

        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
        )

        # 5. Register
        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        return node_id
~~~~~
~~~~~python.new
from typing import Any, Dict, Optional, List

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.jump import JumpSelector
from cascade.spec.ir.graph import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService


class IRGenerator:
    def __init__(self):
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        # id -> NodeIR
        self.nodes: Dict[str, NodeIR] = {}
        # Tracks visited LazyResult UUIDs to their generated Node IDs to handle DAGs
        self._visited: Dict[str, str] = {}

    def generate(self, target: Any) -> GraphIR:
        # If target is a list, treat all items as roots. Otherwise, wrap it.
        targets = target if isinstance(target, (list, tuple)) else [target]
        root_logical_ids = []

        for t in targets:
            if isinstance(t, (LazyResult, MappedLazyResult)):
                root_logical_ids.append(t._uuid)
            self._visit(t)

        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(
            nodes=list(self.nodes.values()), root_logical_ids=root_logical_ids
        )

    def _visit(self, obj: Any) -> Any:
        if isinstance(obj, LazyResult):
            return self._visit_lazy_result(obj)
        elif isinstance(obj, MappedLazyResult):
            return self._visit_mapped_result(obj)
        elif isinstance(obj, Router):
            return self._visit_router(obj)
        elif isinstance(obj, (list, tuple)):
            return type(obj)(self._visit(item) for item in obj)
        elif isinstance(obj, dict):
            return {k: self._visit(v) for k, v in obj.items()}
        else:
            # Literal value
            return obj

    def _visit_router(self, router: Router) -> Dict[str, Any]:
        selector_id = self._visit(router.selector)
        routes = {k: self._visit(v) for k, v in router.routes.items()}
        # Encode Router as a special dictionary structure
        return {
            "$router": True,
            "selector": selector_id,
            "routes": routes,
        }

    def _collect_deps_map(self, lr: Any) -> Dict[str, NodeIR]:
        # We need a dictionary of dependency nodes for the hasher.
        # Since we visited children first, their NodeIRs are already in self.nodes.
        dep_map = {}

        def collect_deps(raw_obj):
            if isinstance(raw_obj, (LazyResult, MappedLazyResult)):
                if raw_obj._uuid in self._visited:
                    node_id = self._visited[raw_obj._uuid]
                    dep_map[raw_obj._uuid] = self.nodes[node_id]
            elif isinstance(raw_obj, Router):
                collect_deps(raw_obj.selector)
                for r in raw_obj.routes.values():
                    collect_deps(r)
            elif isinstance(raw_obj, (list, tuple)):
                for x in raw_obj:
                    collect_deps(x)
            elif isinstance(raw_obj, dict):
                for x in raw_obj.values():
                    collect_deps(x)

        if isinstance(lr, MappedLazyResult):
            for val in lr.mapping_kwargs.values():
                collect_deps(val)
        else:
            for arg in lr.args:
                collect_deps(arg)
            for val in lr.kwargs.values():
                collect_deps(val)

        if lr._condition:
            collect_deps(lr._condition)
        for dep in lr._dependencies:
            collect_deps(dep)
        
        # Collect Jump targets
        # JumpSelector (in lr._jump_selector) contains LazyResults as routes
        if hasattr(lr, "_jump_selector") and isinstance(lr._jump_selector, JumpSelector):
             for route in lr._jump_selector.routes.values():
                 if route:
                    collect_deps(route)

        return dep_map

    def _extract_retry_policy(self, lr: Any) -> Optional[Dict[str, Any]]:
        if lr._retry_policy:
            return {
                "max_attempts": lr._retry_policy.max_attempts,
                "delay": lr._retry_policy.delay,
                "backoff": lr._retry_policy.backoff,
            }
        return None

    def _visit_lazy_result(self, lr: LazyResult) -> str:
        # If already visited, return the cached Node ID
        if lr._uuid in self._visited:
            return self._visited[lr._uuid]

        # 1. Resolve Dependencies (Post-order)
        transformed_args = [self._visit(arg) for arg in lr.args]
        transformed_kwargs = {k: self._visit(v) for k, v in lr.kwargs.items()}

        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))
        
        flow_control = None
        if lr._jump_selector and isinstance(lr._jump_selector, JumpSelector):
            flow_control = {}
            for k, target in lr._jump_selector.routes.items():
                if target:
                     flow_control[k] = self._visit(target)
                else:
                     flow_control[k] = None

        # 2. Analyze Task Definition
        task_def = self.analyzer.analyze(lr.task)

        # 3. Compute Instance Hash
        dep_map = self._collect_deps_map(lr)
        node_id = self.hashing_service.compute_node_instance_hash(task_def, lr, dep_map)

        # 4. Construct NodeIR
        inputs = {}
        for i, val in enumerate(transformed_args):
            inputs[str(i)] = val
        for k, val in transformed_kwargs.items():
            inputs[k] = val

        constraints = {}
        if lr._constraints:
            constraints = lr._constraints.requirements.copy()

        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type="task",
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
        )

        # 5. Register
        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        return node_id

    def _visit_mapped_result(self, lr: MappedLazyResult) -> str:
        if lr._uuid in self._visited:
            return self._visited[lr._uuid]

        transformed_kwargs = {k: self._visit(v) for k, v in lr.mapping_kwargs.items()}

        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

        task_def = self.analyzer.analyze(lr.factory)

        dep_map = self._collect_deps_map(lr)
        node_id = self.hashing_service.compute_node_instance_hash(task_def, lr, dep_map)

        constraints = {}
        if lr._constraints:
            constraints = lr._constraints.requirements.copy()

        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type="map",
            logical_id=lr._uuid,
            inputs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            retry_policy=self._extract_retry_policy(lr),
        )

        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        return node_id
~~~~~

### 下一步建议

现在 `IRGenerator` 已经能够生成包含所有 DSL 特性的 `GraphIR`。下一步，我们应着手实现 **阶段三：桥接适配器**，在 Runtime 中创建一个能够消费这个 `GraphIR` 的适配器，从而验证其完备性。
