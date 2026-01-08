好的，你捕捉到了一个我遗漏的细节。这是一个典型的错误，将 Python 的内置函数 `any` 误用为类型提示 `Any`。我将立即修复它。

这是上一个计划的延续。

## [WIP] fix(typing): 修复 standard_sleep 中的类型提示错误

### 错误分析

`pyright` 报告了一个错误：`Expected class but received "(iterable: Iterable[object], /) -> bool"`。这是因为在 `standard_sleep` 函数签名中，`resources` 参数被错误地注解为 `any`（一个内置函数），而正确的类型提示应该是从 `typing` 模块导入的 `Any`。

### 用户需求

修复 `packages/cascade-std/src/cascade/std/system/time.py` 中遗留的类型错误。

### 评论

这是一个简单但常见的错误。修复它将使类型系统更加完善，并消除所有已知的 `pyright` 错误。

### 目标

1.  在 `packages/cascade-std/src/cascade/std/system/time.py` 文件中，从 `typing` 模块导入 `Any`。
2.  将 `standard_sleep` 函数签名中的 `resources: any` 修改为 `resources: Any`。

### 基本原理

通过使用正确的类型提示，我们将向 `pyright` 提供正确的信息，从而解决这个类型检查错误。

### 标签

#intent/fix #flow/ready #priority/high #comp/std #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 修正 `standard_sleep` 的类型注解

我将修改 `time.py` 文件，导入 `Any` 并更正函数签名。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/time.py
~~~~~
~~~~~python.old
import logging
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.vm.services.contracts import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_sleep(
    inputs: Dict[str, Token], node: PhysicsFuncNode, resources: any
) -> Dict[str, Token]:
    try:
        chronos_queue = resources.get("system.chronos_queue")
~~~~~
~~~~~python.new
import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.vm.services.contracts import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_sleep(
    inputs: Dict[str, Token], node: PhysicsFuncNode, resources: Any
) -> Dict[str, Token]:
    try:
        chronos_queue = resources.get("system.chronos_queue")
~~~~~

### 下一步建议

我们已经处理了所有已知的 `pyright` 错误，并移除了 `add_sink` 机制。现在是验证所有修复是否完整的最佳时机。

我建议你再次运行 `pyright packages` 命令。如果输出是干净的（`0 errors, 0 warnings`），那么我们就可以将这个系列的工作标记为 `[COMMIT]` 并提交。否则，请将新的错误报告发给我。
