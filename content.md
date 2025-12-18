好的，我将开始执行“路线图：可插拔约束处理器架构 (v1.0)”中的第一个里程碑。

这是一个关键的架构重构，它将 `ConstraintManager` 从一个硬编码的实现转变为一个灵活的、由协议驱动的调度中心。这为未来的扩展性和社区贡献奠定了基础，完全符合项目的核心设计原则。

## [WIP] refactor(runtime): 引入可插拔的 ConstraintHandler 协议

### 用户需求
根据“路线图：可插拔约束处理器架构 (v1.0)”，完成“里程碑 1：定义契约 (The Contract)”。

### 评论
这是一个重要的架构演进。将硬编码的约束逻辑解耦为独立的、协议驱动的处理器，是偿还技术债务、拥抱可扩展性的关键一步。此举措将使约束系统更加清晰、可测试，并为未来添加新的控制类型（如速率限制、并发控制）打开大门，而无需修改核心引擎代码。

### 目标
1.  将现有的 `cascade/runtime/constraints.py` 文件重构为一个 `constraints` 包。
2.  在新的包内创建一个 `protocols.py` 文件。
3.  在该文件中定义 `ConstraintHandler` 协议，作为所有未来约束处理器的契约。
4.  确保对 `ConstraintManager` 的现有导入路径不受此次重构的影响。

### 基本原理
为了给新的协议文件 `protocols.py` 和未来的处理器实现提供一个专属的命名空间，我们必须首先将当前的 `constraints.py` 文件转换为一个 Python 包（一个包含 `__init__.py` 的目录）。

具体的重构步骤是：
1.  创建一个新的 `constraints/` 目录。
2.  将原 `constraints.py` 文件移动到新目录中，并重命名为 `manager.py`，以明确其职责。
3.  在 `constraints/` 目录中创建一个 `__init__.py` 文件，该文件从 `manager.py` 中导入并重新导出 `ConstraintManager`。这确保了像 `engine.py` 这样的模块中 `from cascade.runtime.constraints import ConstraintManager` 的导入语句仍然有效，使本次重构对外部透明。
4.  最后，在 `constraints/` 目录中创建新的 `protocols.py` 文件并定义 `ConstraintHandler` 协议。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high #comp/runtime #concept/config #scope/api #ai/instruct #task/domain/runtime #task/object/constraint-system #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 将 `constraints.py` 文件重构为包结构

首先，我们将 `constraints.py` 文件转换为一个包，为新的协议文件和未来的处理器实现提供空间。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-runtime/src/cascade/runtime/constraints && \
mv packages/cascade-runtime/src/cascade/runtime/constraints.py packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~

#### Acts 2: 创建包的 `__init__.py` 以确保向后兼容

我们创建一个 `__init__.py` 文件来重新导出 `ConstraintManager`，这样就不需要修改 `engine.py` 中的导入语句。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/__init__.py
~~~~~
~~~~~python
from .manager import ConstraintManager

__all__ = ["ConstraintManager"]
~~~~~

#### Acts 3: 创建并定义 `ConstraintHandler` 协议

现在，我们创建新的协议文件并定义 `ConstraintHandler` 接口，这是本次重构的核心交付物。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/constraints/protocols.py
~~~~~
~~~~~python
from typing import Protocol, TYPE_CHECKING

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

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Evaluates the constraint against the given task.

        Args:
            task: The task node being considered for execution.
            constraint: The specific constraint instance to evaluate.
            manager: A reference to the parent ConstraintManager, providing access
                     to the overall state if needed.

        Returns:
            True if the task is permitted to run, False if it should be deferred.
        """
        ...
~~~~~

### 下一步建议
我们已经成功定义了契约。接下来的**里程碑 2** 是将当前硬编码在 `ConstraintManager` 中的 `pause` 逻辑迁移到第一个具体的处理器实现 `PauseConstraintHandler` 中。这将是我们新架构的第一个具体应用。
