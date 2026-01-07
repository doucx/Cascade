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
        self._visit(target)
        # Return nodes. The order in self.nodes.values() respects insertion order (Python 3.7+),
        # which corresponds to the post-order traversal (dependencies first),
        # providing a natural topological sort.
        return GraphIR(nodes=list(self.nodes.values()))

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
