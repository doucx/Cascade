from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field

from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.jump import JumpSelector
from cascade.spec.ir.graph import GraphIR, NodeIR
from cascade.reflection import ReflectionAnalyzer, HashingService


@dataclass
class GenerationResult:
    ir: GraphIR
    # Maps node_instance_hash -> Python Callable (the actual code to run)
    executables: Dict[str, Callable] = field(default_factory=dict)


class IRGenerator:
    def __init__(self):
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()
        # id -> NodeIR
        self.nodes: Dict[str, NodeIR] = {}
        # id -> Callable
        self.executables: Dict[str, Callable] = {}
        # Tracks visited LazyResult UUIDs to their generated Node IDs to handle DAGs
        self._visited: Dict[str, str] = {}

    def generate(self, target: Any) -> GenerationResult:
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
        ir = GraphIR(nodes=list(self.nodes.values()), root_logical_ids=root_logical_ids)
        return GenerationResult(ir=ir, executables=self.executables)

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
        if lr._constraints:
            for val in lr._constraints.requirements.values():
                collect_deps(val)
        for dep in lr._dependencies:
            collect_deps(dep)

        # Collect Jump targets
        # JumpSelector (in lr._jump_selector) contains LazyResults as routes
        if hasattr(lr, "_jump_selector") and isinstance(
            lr._jump_selector, JumpSelector
        ):
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

        # Visit dynamic constraints to ensure they are generated
        if lr._constraints:
            for val in lr._constraints.requirements.values():
                self._visit(val)

        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))

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

        # Detect Param nodes
        node_type = "task"
        if task_def.name == "_get_param_value":
            node_type = "param"

        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type=node_type,
            logical_id=lr._uuid,
            args=transformed_args,
            kwargs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            flow_control=flow_control,
            retry_policy=self._extract_retry_policy(lr),
            cache_policy=lr._cache_policy,
        )

        # 5. Register
        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        # Capture executable
        if hasattr(lr.task, "func"):
            self.executables[node_id] = lr.task.func
        else:
            # Fallback for raw callables
            self.executables[node_id] = lr.task

        return node_id

    def _visit_mapped_result(self, lr: MappedLazyResult) -> str:
        if lr._uuid in self._visited:
            return self._visited[lr._uuid]

        transformed_kwargs = {k: self._visit(v) for k, v in lr.mapping_kwargs.items()}

        condition_id = None
        if lr._condition:
            condition_id = self._visit(lr._condition)

        if lr._constraints:
            for val in lr._constraints.requirements.values():
                self._visit(val)

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
            # For map nodes, all inputs are keyword-based
            args=[],
            kwargs=transformed_kwargs,
            constraints=constraints,
            condition=condition_id,
            dependencies=dependency_ids,
            retry_policy=self._extract_retry_policy(lr),
        )

        self.nodes[node_id] = node_ir
        self._visited[lr._uuid] = node_id

        # Capture factory
        self.executables[node_id] = lr.factory

        return node_id
