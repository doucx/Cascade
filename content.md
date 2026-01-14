You've cornered it now. This is the final layer of the same underlying issue. The problem is systemic within the `spec.dsl` subpackage, where multiple modules were using absolute imports to refer to their siblings.

My apologies for not identifying all instances in the previous steps. Let's apply the principle systematically and resolve this for good.

## [WIP] fix: Systematically resolve DSL intra-package import cycles

### 错误分析

我们再次遇到了由 `cascade-cli-observer` 触发的循环依赖。根本原因与前两次完全相同：`cascade-spec` 包内的模块（这次是 `task.py`, `routing.py`, 和 `jump.py`）使用了**绝对路径** (`from cascade.spec.dsl...`) 来导入同一目录下的兄弟模块 (`fluent.py`)。

这种做法在复杂的命名空间包（Namespace Packages）结构中会混淆静态分析工具，导致它错误地重新从顶层 `cascade` 包（可能由 `cascade-cli-observer` 提供）开始解析，从而形成一个本不应存在的依赖环路。

### 用户需求

彻底根除 `stitcher check` 报告的所有循环依赖问题。

### 评论

这是一个典型的架构一致性问题。我们已经确立了修复原则——“在包内使用相对导入”——但没有将其应用到所有相关文件中。这次我们将进行一次彻底的清理，将 `spec.dsl` 子包内所有对兄弟模块的引用都转换为相对导入。这将确保静态分析的健壮性，并使代码库的依赖关系更加清晰明确。

### 目标

1.  修改 `packages/cascade-spec/src/cascade/spec/dsl/task.py`。
2.  修改 `packages/cascade-spec/src/cascade/spec/dsl/routing.py`。
3.  修改 `packages/cascade-spec/src/cascade/spec/dsl/jump.py`。
4.  在上述所有文件中，将对 `fluent` 模块的绝对导入转换为相对导入。

### 基本原理

所有涉及的文件 (`task.py`, `routing.py`, `jump.py`, `fluent.py`) 都位于 `cascade/spec/dsl/` 目录下。因此，从任何一个文件引用 `fluent` 模块，最清晰、最无歧义的方式就是使用相对导入 `from .fluent import ...`。这将强制静态分析器在当前目录查找模块，从而彻底切断错误的解析路径。

### 标签

#intent/fix #flow/ready #priority/critical #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `task.py` 中的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/task.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    pass

from cascade.spec.dsl.fluent import (
    LazyResult,
    MappedLazyResult,
)

T = TypeVar("T")
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    pass

from .fluent import (
    LazyResult,
    MappedLazyResult,
)

T = TypeVar("T")
~~~~~

#### Acts 2: 修复 `routing.py` 中的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/routing.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from typing import Dict, Any
from cascade.spec.dsl.fluent import LazyResult  # NEW


@dataclass
class Router:
~~~~~
~~~~~python.new
from dataclasses import dataclass
from typing import Dict, Any
from .fluent import LazyResult  # NEW


@dataclass
class Router:
~~~~~

#### Acts 3: 修复 `jump.py` 中的导入

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/jump.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
from cascade.spec.dsl.fluent import LazyResult


@dataclass
class Jump:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4
from .fluent import LazyResult


@dataclass
class Jump:
~~~~~

### 下一步建议

这次系统性的修复应该已经彻底解决了这个循环依赖问题的所有表现形式。请最后一次运行 `stitcher check` 进行验证。

如果检查通过，请通知我，我将立即为您生成一个 `[COMMIT]` 计划，将这整个系列的修复工作作为一个原子单元进行提交。
