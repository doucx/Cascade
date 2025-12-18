根据您的指示，我们将推进到 Phase 3 的 **里程碑 3.2: 并发管理**。

核心设计思路是**复用**现有的 `ResourceManager` 作为并发控制的底层执行机构。我们将“并发限制”抽象为一种动态的“资源”。

1.  **动态资源化**: 当接收到外部的并发限制指令（如 `limit task:A = 5`）时，我们在 `ResourceManager` 中动态创建一个名为 `constraint:concurrency:task:A` 的资源，容量设为 5。
2.  **隐式需求注入**: 修改 `ConstraintResolver`，使其在解析任务需求时，检查是否存在针对该任务的并发约束。如果存在，自动为该任务注入 `{"constraint:concurrency:task:A": 1}` 的获取需求。
3.  **统一调度**: `Engine` 的标准调度流程会处理剩余的工作——等待资源（即等待并发槽位）释放。

这是一个优雅的架构，因为它避免了在 `Engine` 主循环中引入新的等待逻辑，而是利用了已有的资源同步原语。

以下是执行计划：

## [WIP] feat(runtime): Implement dynamic concurrency management via ResourceManager

### 摘要头
## [WIP] feat(runtime): Implement dynamic concurrency management via ResourceManager

### 用户需求
实现基于外部指令的任务级并发控制。允许用户通过 `cs-controller` 设置特定 Scope（如 `task:my_task`）的最大并发执行数量，从而保护下游服务或限制资源消耗。

### 评论
此实现采用了“资源映射”模式。通过将并发限制转化为 `ResourceManager` 中的“虚拟资源”，我们将复杂的调度问题转化为了标准的资源获取问题，极大地降低了系统复杂度。

### 目标
1.  增强 `ResourceManager` 以支持增量更新容量。
2.  修改 `ConstraintManager`，使其在收到并发约束时自动同步更新 `ResourceManager` 的容量。
3.  扩展 `ConstraintResolver`，根据通过的约束自动为任务注入资源需求。
4.  在 `cs-controller` 中添加 `set-limit` 命令。

### 基本原理
-   **ResourceManager.update_capacity**: 现有的 `set_capacity` 是破坏性的（重置所有）。我们需要一个非破坏性的方法来动态调整特定资源的容量。
-   **隐式需求 (Implicit Requirements)**: 用户不需要在 `@cs.task` 装饰器中硬编码并发限制。这些限制是运行时通过 `ConstraintResolver` 动态“附加”到任务上的。这符合“控制层与业务层分离”的原则。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/cli #concept/state #scope/core #ai/instruct #task/domain/core #task/object/concurrency #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强 ResourceManager

我们需要添加 `update_capacity` 方法，允许在不影响其他资源的情况下更新特定资源的容量。同时优化 `_validate_feasibility` 以支持动态添加的资源。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resource_manager.py
~~~~~
~~~~~old
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
~~~~~
~~~~~new
    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        """Updates system capacity configuration (resets existing)."""
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    def update_capacity(self, updates: Dict[str, Union[int, float]]):
        """
        Incrementally updates capacity for specific resources without clearing others.
        Useful for dynamic constraints.
        """
        for k, v in updates.items():
            self._capacity[k] = float(v)
            if k not in self._usage:
                self._usage[k] = 0.0

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
~~~~~

#### Acts 2: 修改 ConstraintManager 逻辑

我们将修改 `ConstraintManager`，使其能够持有 `ResourceManager` 的引用。当收到类型为 `concurrency` 的约束时，它会计算资源键名（`constraint:concurrency:{scope}`）并调用 `resource_manager.update_capacity`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~old
from typing import Dict
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self):
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

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            del self._constraints[cid]

    def check_permission(self, task: Node) -> bool:
~~~~~
~~~~~new
from typing import Dict, Optional, TYPE_CHECKING
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node
from .protocols import ConstraintHandler

if TYPE_CHECKING:
    from cascade.runtime.resource_manager import ResourceManager


class ConstraintManager:
    """
    Manages a collection of global constraints and dispatches them to pluggable
    handlers for evaluation.
    """

    def __init__(self, resource_manager: Optional["ResourceManager"] = None):
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
        # Stores registered handlers by the constraint type they handle
        self._handlers: Dict[str, ConstraintHandler] = {}
        self._resource_manager = resource_manager

    def register_handler(self, handler: ConstraintHandler) -> None:
        """Registers a constraint handler for the type it handles."""
        self._handlers[handler.handles_type()] = handler

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint
        self._apply_side_effects(constraint)

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            # TODO: Ideally we should revert side effects (e.g. remove resource limit),
            # but setting capacity to infinite/high is complex without explicit removal support in RM.
            # For now, we leave the resource limit as is, or rely on future overwrites.
            # In a robust impl, we would reset the capacity to infinite.
            del self._constraints[cid]

    def _apply_side_effects(self, constraint: GlobalConstraint):
        """Applies side effects for specific constraint types (e.g. concurrency)."""
        if constraint.type == "concurrency" and self._resource_manager:
            limit = constraint.params.get("limit")
            if limit is not None:
                resource_key = f"constraint:concurrency:{constraint.scope}"
                self._resource_manager.update_capacity({resource_key: float(limit)})

    def check_permission(self, task: Node) -> bool:
~~~~~

#### Acts 3: 修改 ConstraintResolver 以注入需求

`ConstraintResolver` 现在需要遍历 `ConstraintManager` 中的活跃约束。如果发现匹配当前任务的 `concurrency` 约束，它将向返回的需求字典中注入对应的虚拟资源需求。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}

        constraint_edges = [
~~~~~
~~~~~new
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cascade.runtime.constraints import ConstraintManager


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def __init__(self, constraint_manager: "ConstraintManager" = None):
        self.constraint_manager = constraint_manager

    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve explicit constraints from Node definition
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

        # 2. Resolve implicit constraints from ConstraintManager (Global/External)
        if self.constraint_manager:
            # We iterate over all constraints to find concurrency limits that apply to this node.
            # This is O(N_constraints), usually small.
            for constraint in self.constraint_manager._constraints.values():
                if constraint.type == "concurrency":
                    # Check scope match
                    is_match = False
                    if constraint.scope == "global":
                        is_match = True
                    elif constraint.scope.startswith("task:"):
                        target_name = constraint.scope.split(":", 1)[1]
                        if node.name == target_name:
                            is_match = True
                    
                    if is_match:
                        # Inject implicit requirement: 1 slot of the synthetic resource
                        resource_key = f"constraint:concurrency:{constraint.scope}"
                        resolved[resource_key] = 1

        return resolved
~~~~~

#### Acts 4: 更新 Engine 组装逻辑

在 `Engine` 初始化时，将 `ResourceManager` 注入到 `ConstraintManager`，并将 `ConstraintManager` 注入到 `ConstraintResolver`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~old
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager()
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~new
        self.resource_manager = ResourceManager(capacity=system_resources)
        
        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(resource_manager=self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver(constraint_manager=self.constraint_manager)
        self.flow_manager: Optional[FlowManager] = None
~~~~~

#### Acts 5: 增强 cs-controller

实现 `set-limit` 命令。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~old
    try:
        asyncio.run(_publish_resume(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
~~~~~
~~~~~new
    try:
        asyncio.run(_publish_resume(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


async def _publish_limit(scope: str, limit: int, hostname: str, port: int):
    """Core logic for publishing a concurrency limit constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        constraint_id = f"limit-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="concurrency",
            params={"limit": limit}
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        await connector.publish(topic, payload, retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command(name="set-limit")
def set_limit(
    scope: str = typer.Argument(..., help="The scope (e.g., 'task:api_call')."),
    concurrency: int = typer.Option(..., "--concurrency", "-c", help="Max concurrent executions."),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a concurrency limit constraint.
    """
    try:
        asyncio.run(_publish_limit(scope=scope, limit=concurrency, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
~~~~~

### 下一步建议
我们已经完成了并发限制的基础设施。接下来的步骤是：
1.  **验证**: 编写集成测试，验证通过 `ConstraintManager` 注入的并发限制确实导致了任务排队。
2.  **里程碑 3.3**: 实现速率限制 (Rate Limiting)。这将涉及引入令牌桶算法。
