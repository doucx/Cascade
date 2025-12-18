您指出的问题非常正确，我的上一个计划中 `patch_file` 指令缺少必要的 `old_string` 和 `new_string` 参数，导致操作失败。非常抱歉，这是我的疏忽。

我已经审查并修正了整个计划，确保所有文件操作指令都是完整和正确的。对于修改较大的文件，我已遵循协议改用 `write_file` 以确保稳健性。

这是修正后的完整计划：

## [WIP] feat: 实现并发管理与动态资源约束

### 用户需求
实现“并发管理”里程碑。允许用户通过 MQTT 发布 `concurrency` 类型的约束，从而限制特定 Scope 下任务的并发执行数量。

### 评论
这是 Phase 3 的核心功能之一。通过将并发限制抽象为动态资源，我们可以复用现有的 `ResourceManager` 及其健壮的 `asyncio.Condition` 等待机制，而无需引入新的调度队列逻辑。这体现了“组合优于重新发明”的哲学。

### 目标
1.  扩展 `ResourceManager` 以支持动态更新资源容量。
2.  升级 `ConstraintHandler` 协议，使其能够参与资源需求的定义。
3.  实现 `ConcurrencyConstraintHandler`，负责将并发约束转换为资源需求。
4.  集成 `ConstraintManager` 与 `ResourceManager` 和 `ConstraintResolver`。

### 基本原理
我们将并发限制建模为一种特殊的资源（例如 `constraint:concurrency:task:my_task`）。
1.  当接收到并发约束时，`ConstraintManager` 通知 Handler，Handler 在 `ResourceManager` 中创建对应的资源池。
2.  当任务准备执行时，`ConstraintResolver` 询问 Handler，Handler 发现该任务匹配约束 Scope，于是向任务的资源需求中注入 1 个单位的该资源。
3.  `Engine` 现有的资源获取逻辑会自动处理等待和排队。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/core #task/object/concurrency-control #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 增强 ResourceManager

我们将为 `ResourceManager` 添加一个 `update_resource` 方法，以便动态添加或更新单个资源的容量。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~python
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
~~~~~
~~~~~python
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    def update_resource(self, name: str, capacity: float):
        """Dynamically updates or creates a single resource's capacity."""
        self._capacity[name] = float(capacity)
        if name not in self._usage:
            self._usage[name] = 0.0
        # If we reduced capacity below current usage, that's allowed (soft limit),
        # but new acquisitions will block.

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
~~~~~

#### Acts 2: 扩展 ConstraintHandler 协议

由于协议的结构性变更较大，我们使用 `write_file` 完整覆盖，以确保其清晰和正确。新协议将支持约束的生命周期事件和资源需求的动态注入。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/protocols.py
~~~~~
~~~~~python
from typing import Protocol, TYPE_CHECKING, Dict, Any

from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint

if TYPE_CHECKING:
    from .manager import ConstraintManager


class ConstraintHandler(Protocol):
    """
    Protocol for a pluggable handler that implements the logic for a specific
    type of global constraint (e.g., "pause", "rate_limit").
    """

    def handles_type(self) -> str:
        """Returns the constraint type this handler is responsible for."""
        ...

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        """Called when a new constraint of this type is added or updated."""
        ...

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        """Called when a constraint is removed."""
        ...

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Evaluates the constraint against the given task.
        Returns: True if permitted, False if deferred.
        """
        ...

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        """
        Allows the handler to inject dynamic resource requirements for the task.
        Modifies the 'requirements' dictionary in-place.
        """
        ...
~~~~~

#### Acts 3: 更新 ConstraintManager

`ConstraintManager` 的职责有较大调整，同样使用 `write_file` 进行重写。它现在需要持有 `ResourceManager` 的引用，并负责调用 Handler 的新方法。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler
from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            constraint = self._constraints[cid]
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.on_constraint_remove(constraint, self)
            del self._constraints[cid]

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints against a task. If any handler denies
        permission, the task is deferred.
        """
        # TODO: Implement expiry logic (check constraint.expires_at)

        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if not handler:
                continue  # No handler for this constraint type, so we ignore it

            # If the handler denies permission, we stop immediately.
            if not handler.check_permission(task, constraint, self):
                return False  # Execution is not permitted

        # If no handler denied permission, permit execution.
        return True

    def get_extra_requirements(self, task: Node) -> Dict[str, Any]:
        """
        Collects dynamic resource requirements from all applicable constraints.
        """
        requirements: Dict[str, Any] = {}
        for constraint in self._constraints.values():
            handler = self._handlers.get(constraint.type)
            if handler:
                handler.append_requirements(task, constraint, requirements, self)
        return requirements
~~~~~

#### Acts 4: 实现 ConcurrencyConstraintHandler 并更新 PauseHandler

我们创建新的 `handlers.py` 文件，其中包含新的 `ConcurrencyConstraintHandler` 和符合新协议的 `PauseConstraintHandler`。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
from typing import TYPE_CHECKING, Dict, Any

from .protocols import ConstraintHandler
from cascade.graph.model import Node
from cascade.spec.constraint import GlobalConstraint


if TYPE_CHECKING:
    from .manager import ConstraintManager


class PauseConstraintHandler(ConstraintHandler):
    """
    Handles the 'pause' constraint type.
    It can pause execution globally or for a specific task.
    """

    def handles_type(self) -> str:
        return "pause"

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        pass

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        pass


class ConcurrencyConstraintHandler(ConstraintHandler):
    """
    Handles the 'concurrency' constraint type.
    Maps concurrency limits to dynamic system resources.
    """

    def handles_type(self) -> str:
        return "concurrency"

    def _get_resource_name(self, constraint: GlobalConstraint) -> str:
        return f"constraint:concurrency:{constraint.scope}"

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        limit = constraint.params.get("limit", 1)
        res_name = self._get_resource_name(constraint)
        manager.resource_manager.update_resource(res_name, limit)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        # We don't necessarily delete the resource, but we could set capacity to infinite?
        # Or just leave it. If the constraint is gone, tasks won't ask for it anymore.
        # So doing nothing is safe and simpler.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        # Concurrency is handled via resource acquisition, not boolean permission checks.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        # Check scope match
        scope = constraint.scope
        is_match = False

        if scope == "global":
            is_match = True
        elif scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                is_match = True
        
        if is_match:
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~

#### Acts 5: 更新 ConstraintResolver

Resolver 现在需要调用 Manager 来获取额外的动态需求，并将其与任务自身的静态需求合并。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}

        constraint_edges = [
            e
            for e in graph.edges
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )

                if constraint_edge is None:
                    raise RuntimeError(
                        f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                    )

                if state_backend.has_result(constraint_edge.source.id):
                    resolved[res] = state_backend.get_result(constraint_edge.source.id)
                else:
                    raise DependencyMissingError(
                        node.id, f"constraint:{res}", constraint_edge.source.id
                    )
            else:
                resolved[res] = amount
        return resolved
~~~~~
~~~~~python
    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend, constraint_manager: "ConstraintManager" = None
    ) -> Dict[str, Any]:
        """
        Resolves resource requirements from:
        1. Node-level .with_constraints() (static & dynamic)
        2. Global constraints (via ConstraintManager)
        """
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            constraint_edges = [
                e
                for e in graph.edges
                if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
            ]

            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    constraint_edge = next(
                        (e for e in constraint_edges if e.arg_name == res), None
                    )

                    if constraint_edge is None:
                        raise RuntimeError(
                            f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                        )

                    if state_backend.has_result(constraint_edge.source.id):
                        resolved[res] = state_backend.get_result(constraint_edge.source.id)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", constraint_edge.source.id
                        )
                else:
                    resolved[res] = amount
        
        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            # TODO: Handle conflict resolution? For now, we assume disjoint keys or additive.
            # But concurrency resources have unique names, so conflicts are unlikely.
            resolved.update(extra)

        return resolved
~~~~~

#### Acts 6: 更新 Engine

最后，我们将 `ConstraintManager` 的实例化和 `ConstraintResolver` 的调用更新，以集成所有新组件。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.constraints.handlers import PauseConstraintHandler
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager()
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~python
from cascade.runtime.constraints.handlers import PauseConstraintHandler, ConcurrencyConstraintHandler
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        requirements = self.constraint_resolver.resolve(node, graph, state_backend)
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)
~~~~~

### 下一步建议
我们已经完成了并发管理的核心逻辑。下一步是为这个功能编写集成测试，验证通过 `ConstraintManager` 动态添加的并发限制确实能生效。

建议创建一个新的测试文件 `tests/py/runtime/test_engine_concurrency.py`。
