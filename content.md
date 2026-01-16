好的，我将优先解决 `ConstraintManager` 与 `ConstraintHandler` 之间的双文件循环依赖。

你的分析完全正确：即使使用了 `TYPE_CHECKING`，接口（`ConstraintHandler`）也不应该知道其具体实现（`ConstraintManager`）。这违反了依赖倒置原则，造成了逻辑上的强耦合。

为了打破这个循环，我将引入一个中立的上下文协议（`HandlerContext`），该协议将作为 `Manager` 和 `Handler` 之间的桥梁。`Manager` 将实现此协议，而 `Handler` 将依赖此协议，从而实现依赖关系的单向流动。

## [WIP] refactor(runtime): 通过上下文协议解耦 ConstraintManager 与 Handler

### 错误分析
`ConstraintManager` (实现) 和 `ConstraintHandler` (协议) 之间存在一个双向的类型导入。`Manager` 需要 `Handler` 的类型来管理处理程序，而 `Handler` 协议的方法签名中又反向引用了 `Manager` 的类型。这创建了一个逻辑循环，违反了依赖倒置原则，即高层抽象（协议）不应依赖于底层细节（具体实现）。

### 用户需求
彻底消除 `ConstraintManager` 和 `ConstraintHandler` 之间的循环依赖，即使是在 `TYPE_CHECKING` 块中。

### 评论
这是一个经典的架构重构，旨在提升系统的模块化和可测试性。通过引入一个专门的 `HandlerContext` 协议，我们不仅解决了循环依赖，还使 `ConstraintHandler` 的接口更加清晰和稳定——它只声明自己需要什么服务，而不关心是谁提供了这些服务。

### 目标
1.  在 `protocols.py` 中创建一个新的 `HandlerContext` 协议，定义 `Handler` 所需的回调服务（如 `request_wakeup` 和访问 `ResourceManager`）。
2.  修改 `ConstraintHandler` 协议，使其所有方法都接受 `HandlerContext` 作为参数，而不是具体的 `ConstraintManager`。
3.  让 `ConstraintManager` 类显式实现 `HandlerContext` 协议。
4.  更新 `handlers.py` 中的所有具体处理程序，使其符合新的 `ConstraintHandler` 协议签名，并通过 `HandlerContext` 与 `Manager` 交互。

### 基本原理
此方案遵循**依赖倒置原则**。我们将依赖关系从：
`Manager <--> Handler`
转变为：
`Manager --> HandlerContext <-- Handler`
现在，`Manager` 和 `Handler` 都依赖于 `HandlerContext` 这个抽象，它们之间不再有直接的依赖关系，从而彻底消除了循环。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/dependency-inversion #scope/core #ai/brainstorm #task/domain/runtime #task/object/circular-dependency #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构协议层 (`protocols.py`)

我们将完全重写 `protocols.py`，引入 `HandlerContext` 并更新 `ConstraintHandler`，使其完全自包含。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/protocols.py
~~~~~
~~~~~python
from typing import Protocol, TYPE_CHECKING, Dict, Any

from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint

if TYPE_CHECKING:
    from ..resources.manager import ResourceManager


class HandlerContext(Protocol):
    """
    Defines the services a ConstraintHandler can request from its manager.
    This acts as an inversion of control mechanism to break circular dependencies.
    """

    def request_wakeup(self, delay: float) -> None: ...
    def get_resource_manager(self) -> "ResourceManager": ...


class ConstraintHandler(Protocol):
    def handles_type(self) -> str: ...

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None: ...

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None: ...

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool: ...

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None: ...
~~~~~

#### Acts 2: 适配 `ConstraintManager` (`manager.py`)

现在，我们让 `ConstraintManager` 实现新的 `HandlerContext` 协议。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/manager.py
~~~~~
~~~~~python.old
import time
from typing import Dict, Any
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.execution.graph.model.model import Node
from .protocols import ConstraintHandler
from ..resources.manager import ResourceManager


class ConstraintManager:
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
~~~~~
~~~~~python.new
import time
from typing import Dict, Any
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.execution.graph.model.model import Node
from .protocols import ConstraintHandler, HandlerContext
from ..resources.manager import ResourceManager


class ConstraintManager(HandlerContext):
    def __init__(self, resource_manager: ResourceManager):
        self.resource_manager = resource_manager
        # Stores active constraints by their unique ID
        self._constraints: Dict[str, GlobalConstraint] = {}
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/manager.py
~~~~~
~~~~~python.old
    def set_wakeup_callback(self, callback: Any) -> None:
        self._wakeup_callback = callback

    def request_wakeup(self, delay: float) -> None:
        if self._wakeup_callback:
            import asyncio
~~~~~
~~~~~python.new
    def set_wakeup_callback(self, callback: Any) -> None:
        self._wakeup_callback = callback

    def get_resource_manager(self) -> ResourceManager:
        return self.resource_manager

    def request_wakeup(self, delay: float) -> None:
        if self._wakeup_callback:
            import asyncio
~~~~~

#### Acts 3: 更新所有处理程序实现 (`handlers.py`)

最后，我们更新所有具体的 `ConstraintHandler` 实现，使其符合新的协议签名。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
~~~~~
~~~~~python.old
from typing import TYPE_CHECKING, Dict, Any, Optional
import fnmatch
from cascade.bus.feedback import bus

from cascade.runtime.services.constraints.protocols import ConstraintHandler
from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.runtime.services.constraints.rate_limiter import RateLimiter


if TYPE_CHECKING:
    from cascade.runtime.services.constraints.manager import ConstraintManager
~~~~~
~~~~~python.new
from typing import TYPE_CHECKING, Dict, Any, Optional
import fnmatch
from cascade.bus.feedback import bus

from .protocols import ConstraintHandler, HandlerContext
from cascade.execution.graph.model.model import Node
from cascade.spec.dsl.constraint import GlobalConstraint
from .rate_limiter import RateLimiter


if TYPE_CHECKING:
    pass
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
~~~~~
~~~~~python.old
    def handles_type(self) -> str:
        return "pause"

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:  # pragma: no cover
        pass

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:  # pragma: no cover
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        if _matches(constraint.scope, task.name):
            return False
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:  # pragma: no cover
        pass
~~~~~
~~~~~python.new
    def handles_type(self) -> str:
        return "pause"

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        pass

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:
        if _matches(constraint.scope, task.name):
            return False
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:  # pragma: no cover
        pass
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
~~~~~
~~~~~python.old
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
    ) -> None:  # pragma: no cover
        # We don't necessarily delete the resource, but we could set capacity to infinite?
        # Or just leave it. If the constraint is gone, tasks won't ask for it anymore.
        # So doing nothing is safe and simpler.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:  # pragma: no cover
        # Concurrency is handled via resource acquisition, not boolean permission checks.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:
        if _matches(constraint.scope, task.name):
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~
~~~~~python.new
    def _get_resource_name(self, constraint: GlobalConstraint) -> str:
        return f"constraint:concurrency:{constraint.scope}"

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:
        limit = constraint.params.get("limit", 1)
        res_name = self._get_resource_name(constraint)
        context.get_resource_manager().update_resource(res_name, limit)

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        # We don't necessarily delete the resource, but we could set capacity to infinite?
        # Or just leave it. If the constraint is gone, tasks won't ask for it anymore.
        # So doing nothing is safe and simpler.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:  # pragma: no cover
        # Concurrency is handled via resource acquisition, not boolean permission checks.
        return True

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:
        if _matches(constraint.scope, task.name):
            res_name = self._get_resource_name(constraint)
            # We require 1 slot of this concurrency resource
            requirements[res_name] = 1
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
~~~~~
~~~~~python.old
    def _get_scope_key(self, constraint: GlobalConstraint) -> str:
        return constraint.scope

    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))
~~~~~
~~~~~python.new
    def _get_scope_key(self, constraint: GlobalConstraint) -> str:
        return constraint.scope

    def on_constraint_add(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/handlers.py
~~~~~
~~~~~python.old
        self.limiter.update_bucket(
            self._get_scope_key(constraint), rate_hertz, capacity_val
        )

    def on_constraint_remove(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:  # pragma: no cover
        # Currently RateLimiter doesn't support deleting buckets, which is fine.
        # It just won't be used.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        if not _matches(constraint.scope, task.name):
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))

        if wait_time == 0.0:
            return True
        else:
            # We are rate limited. Request a wakeup when tokens should be available.
            manager.request_wakeup(wait_time)
            return False

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        manager: "ConstraintManager",
    ) -> None:  # pragma: no cover
        pass
~~~~~
~~~~~python.new
        self.limiter.update_bucket(
            self._get_scope_key(constraint), rate_hertz, capacity_val
        )

    def on_constraint_remove(
        self, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> None:  # pragma: no cover
        # Currently RateLimiter doesn't support deleting buckets, which is fine.
        # It just won't be used.
        pass

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, context: "HandlerContext"
    ) -> bool:
        if not _matches(constraint.scope, task.name):
            return True

        # Try acquire
        wait_time = self.limiter.try_acquire(self._get_scope_key(constraint))

        if wait_time == 0.0:
            return True
        else:
            # We are rate limited. Request a wakeup when tokens should be available.
            context.request_wakeup(wait_time)
            return False

    def append_requirements(
        self,
        task: Node,
        constraint: GlobalConstraint,
        requirements: Dict[str, Any],
        context: "HandlerContext",
    ) -> None:  # pragma: no cover
        pass
~~~~~

### 下一步建议
1.  **静态分析验证**: 再次运行强耦合组件检查，确认 `ConstraintManager` 和 `ConstraintHandler` 之间的循环依赖已被彻底解决。
2.  **单元测试**: 重点运行 `cascade-runtime` 的测试，特别是与约束管理相关的测试用例，确保新的上下文协议被正确实现和调用。
3.  **解决下一个循环**: 准备处理下一个、也是最后一个主要的循环依赖问题：`Engine` 与 `VMExecutionStrategy` 之间的包初始化冲突。
