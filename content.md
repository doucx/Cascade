好的，我们正式启动第三阶段：**约束与环境感知**。

此阶段的核心目标是建立一个反馈回路，让 Cascade 能够接收外部指令并动态调整其执行行为，从一个纯粹的工作流执行器演变为一个具备环境感知能力的自适应系统。

根据我们的技术路线图，第一步是构建此系统的基础：定义核心数据模型和管理组件。我将生成一个计划来完成这项基础工作。

## [WIP] feat: 定义约束系统的数据模型和管理器

### 用户需求
正式启动“第三阶段：约束与环境感知”的开发工作。

### 评论
这是 Cascade 架构演进中的一个关键里程碑。通过引入约束系统，我们为实现“向下因果”（即由宏观环境参数影响微观任务行为）奠定了基础。这将极大地增强 Cascade 在复杂、动态环境中的可操作性和健壮性。

### 目标
1.  在 `cascade.spec.constraint` 中定义 `GlobalConstraint` 数据模型，作为系统中所有约束的标准化表示。
2.  创建一个新的 `cascade.runtime.constraints` 模块，并在其中实现 `ConstraintManager` 类。
3.  `ConstraintManager` 将负责在内存中存储和更新全局约束。
4.  为 `ConstraintManager` 实现一个 `check_permission` 方法的占位符，为后续与调度循环的集成做准备。

### 基本原理
我们遵循增量开发的原则。在将约束逻辑集成到 `Engine` 的调度循环之前，我们必须先有明确定义的数据结构 (`GlobalConstraint`) 和一个负责管理这些数据状态的中心化组件 (`ConstraintManager`)。这个计划通过创建这些基础构建块，为后续的功能实现提供了一个稳定、清晰的接口，实现了关注点分离。

### 标签
#intent/architect #flow/ready #priority/high
#comp/interfaces #comp/runtime #concept/constraints #scope/api
#ai/instruct
#task/domain/runtime #task/object/constraint-system #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义数据模型并创建管理器

首先，我们将扩展 `cascade-interfaces` 包，在 `constraint.py` 中添加新的 `GlobalConstraint` 数据类。然后，在 `cascade-runtime` 包中创建一个新的 `constraints.py` 文件，并实现 `ConstraintManager` 的基础结构。

~~~~~act
write_file
packages/cascade-interfaces/src/cascade/spec/constraint.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ResourceConstraint:
    """
    Defines the resource requirements for a Task.

    The keys represent the resource name (e.g., "memory_gb", "gpu_count")
    and the values represent the required amount (literal value or a LazyResult).
    """

    requirements: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.requirements

    def __bool__(self):
        return not self.is_empty()


def with_constraints(**kwargs) -> ResourceConstraint:
    """Helper function for task definitions."""
    return ResourceConstraint(requirements=kwargs)


@dataclass
class GlobalConstraint:
    """
    Represents a global, environment-aware constraint that can affect workflow execution.
    """

    id: str
    scope: str  # e.g., "global", "project:quipu", "task:openai_request"
    type: str  # "concurrency", "rate_limit", "pause"
    params: Dict[str, Any]  # e.g., {"limit": 5, "window": 60}
    expires_at: Optional[float] = None
~~~~~
~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints.py
~~~~~
~~~~~python
from typing import Dict, Optional
from cascade.spec.constraint import GlobalConstraint
from cascade.graph.model import Node


class ConstraintManager:
    """
    Manages a collection of global constraints that affect workflow execution.
    """

    def __init__(self):
        # Stores constraints by their unique ID for easy updates
        self._constraints: Dict[str, GlobalConstraint] = {}

    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """
        Adds a new constraint or updates an existing one.
        """
        self._constraints[constraint.id] = constraint

    def check_permission(self, task: Node) -> bool:
        """
        Evaluates all active constraints to determine if a given task
        is currently allowed to execute.

        TODO: Implement full evaluation logic based on constraint scope and type.
              For now, it's permissive.
        """
        # Placeholder logic: always allow execution
        return True
~~~~~

### 下一步建议
我们已经成功定义了约束系统的数据模型和管理器。接下来的关键一步是**将 `ConstraintManager` 集成到 `Engine` 的核心生命周期中**。

具体计划如下：
1.  **引擎集成**: 修改 `Engine` 的 `__init__` 方法，使其可以接收一个 `ConstraintManager` 实例。
2.  **调度循环修改**: 在 `Engine._execute_graph` 的主循环中，在任务提交给 `Executor` 之前，调用 `constraint_manager.check_permission(node)`。
3.  **行为实现**: 如果 `check_permission` 返回 `False`，任务将被暂时挂起，而不是提交执行。

如果你同意，我将生成执行此集成步骤的计划。
