简要回答：
这是一个典型的文件/目录命名冲突导致的导入错误。我将重构 `middleware` 模块，将其定义移动到 `base.py` 中，并清理冲突的文件，彻底解决导入路径问题并消除循环依赖风险。

## [WIP] fix(vm): Resolve middleware import conflict and restructure package

### 错误分析
用户遇到了 `ModuleNotFoundError: No module named 'cascade.vm.middleware.middleware'`。
根本原因是文件系统结构的歧义：
1.  我们在 `src/cascade/vm/` 下创建了一个名为 `middleware.py` 的**文件**。
2.  同时我们又创建了一个名为 `middleware/` 的**目录**（包），并在其中放了 `__init__.py`。
3.  在 Python 中，当导入 `cascade.vm.middleware` 时，它优先加载了包（目录）。
4.  也就是加载了 `middleware/__init__.py`。
5.  该 `__init__.py` 中有一句 `from .middleware import ...`。这意味着它试图在 `middleware/` **目录内部**寻找一个叫 `middleware.py` 的文件。
6.  但那个定义文件实际上是在上一层目录（作为同名文件存在），而不是在包内部。

这种情况也极易引发循环依赖和命名空间混淆。

### 解决方案
1.  **重构结构**: 将原 `middleware.py` 的内容移动到 `src/cascade/vm/middleware/base.py` 中。这符合“包内模块”的标准组织方式。
2.  **修正入口**: 修改 `src/cascade/vm/middleware/__init__.py`，使其从 `.base` 而非 `.middleware` 导入。
3.  **清理**: 删除造成冲突的 `src/cascade/vm/middleware.py` 文件。

### 影响范围
*   `cascade-vm` 包结构。
*   依赖于中间件定义的代码 (`cascade.vm.machine`, `cascade.vm.middleware.standard`) 不需要修改导入语句，因为 `__init__.py` 依然会导出相同的符号。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #scope/core #ai/instruct #task/domain/core #task/object/middleware #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `base.py` 并修复 `__init__.py`

我们将定义移入包内的一个新文件 `base.py`，并更新包的导出逻辑。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/base.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, List, Dict, Protocol, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from cascade.spec.blueprint import Instruction
    from cascade.vm.machine import Frame

# Handler Type: A function that takes no args (context is implicit/closed over) and returns Awaitable result
NextHandler = Callable[[], Awaitable[Any]]


@dataclass
class ExecutionContext:
    """
    Carries the state of a single instruction execution through the middleware pipeline.
    """
    instruction: "Instruction"
    frame: "Frame"
    symbol_table: Dict[str, Callable]
    
    # Resolvable inputs. Middleware can modify these in-place.
    # The pipeline starts with these populated from the instruction's operands.
    resolved_args: List[Any] = field(default_factory=list)
    resolved_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # Shared storage for middlewares to pass data down the line (e.g. dynamic constraints)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Middleware(Protocol):
    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        ...
~~~~~

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/__init__.py
~~~~~
~~~~~python
from .base import Middleware, ExecutionContext, NextHandler

__all__ = ["Middleware", "ExecutionContext", "NextHandler"]
~~~~~

#### Acts 2: 修复 `standard.py` 中的引用

虽然 `__init__.py` 导出了这些符号，但在包内部（`standard.py`）为了避免循环依赖和明确性，最好直接从 `.base` 导入，或者确认它从 `cascade.vm.middleware` 导入时不会出问题。
当前 `standard.py` 的导入是：
`from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler`
这是绝对导入，会经过 `__init__.py`。由于 `__init__.py` 现在依赖 `.base`，而 `standard.py` 在 `base.py` 之后被使用，理论上没问题。
但为了代码的清晰和稳健（特别是在重构期间），我们更新 `standard.py` 使其直接引用 `.base`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/middleware/standard.py
~~~~~
~~~~~python.old
import asyncio
from typing import Any, Dict, Optional
from cascade.spec.blueprint import ResourceOperand, ContextOperand
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler
from cascade.vm.protocols import ResourceManager, ConstraintManager

class ArgumentResolutionMiddleware(Middleware):
~~~~~
~~~~~python.new
import asyncio
from typing import Any, Dict, Optional
from cascade.spec.blueprint import ResourceOperand, ContextOperand
from cascade.vm.middleware.base import Middleware, ExecutionContext, NextHandler
from cascade.vm.protocols import ResourceManager, ConstraintManager

class ArgumentResolutionMiddleware(Middleware):
~~~~~

#### Acts 3: 删除冲突文件

最后，删除那个导致一切混乱的文件。

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/middleware.py
~~~~~

### 下一步建议
现在包及模块结构已修复，应该再次运行测试。
`pytest packages/cascade-vm/tests/integration/test_vm_capabilities.py`
