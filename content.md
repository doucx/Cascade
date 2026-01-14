Your analysis is sharp. The first fix exposed a deeper, more subtle circular dependency rooted in how Python's namespace packages are resolved by static analysis tools.

You've correctly identified the new error loop. Let's break it down.

## [WIP] fix: Resolve circular dependency between spec and execution-graph (Part 2)

### 错误分析

在修复了 `interfaces.py` 的直接反向依赖后，`stitcher` 工具揭示了第二个、更隐蔽的循环依赖。

1.  **起点**: `packages/cascade-cli-observer/src/cascade/__init__.py` 导入了 `cascade.sdk`。
2.  **路径**: `sdk` -> `spec.dsl.task` -> `spec.dsl.fluent`。
3.  **闭环点**: `packages/cascade-spec/src/cascade/spec/dsl/fluent.py` 文件中，有一行 `from cascade.spec.runtime.interfaces import CachePolicy`。
4.  **根本原因**: 这是一个**命名空间解析环路**。当静态分析器在 `cascade-spec` 包内部处理这个绝对导入 `cascade.spec...` 时，它会从 `sys.path` 的根部重新查找 `cascade` 命名空间。由于 `cascade-cli-observer` 也在路径上，并且提供了一个 `cascade/__init__.py`，分析器可能会错误地将 `cascade-cli-observer` 作为 `cascade` 命名空间的起点，从而进入了 `__init__.py` -> `sdk` -> ... 的循环，最终回到 `fluent.py`。

问题的核心是 `fluent.py` 中一个**包内**的依赖，却使用了**绝对路径**导入，这在复杂的命名空间包（Namespace Packages）场景下会给静态分析工具带来歧义。

### 用户需求

继续解决 `stitcher check` 报告的循环依赖问题。

### 评论

这是一个典型的由命名空间包和静态分析工具交互产生的复杂问题。解决方案非常直接：当一个模块需要导入同一包内的另一个模块时，应优先使用**相对导入**（relative import）。

相对导入的语法（如 `from ..runtime import ...`）明确地告诉 Python 解释器和静态分析器：“从当前位置开始查找，不要去 `sys.path` 里重新搜索顶级包”。这消除了路径解析的歧义，从而切断了错误的依赖环路。

### 目标

1.  修改 `packages/cascade-spec/src/cascade/spec/dsl/fluent.py` 文件。
2.  将对 `interfaces` 模块的绝对导入 `from cascade.spec.runtime.interfaces import CachePolicy` 更改为相对导入。

### 基本原理

`fluent.py` 位于 `cascade/spec/dsl/`。它需要导入的 `interfaces.py` 位于 `cascade/spec/runtime/`。从 `dsl` 目录出发，需要先向上返回到 `spec` 目录，然后再进入 `runtime` 目录。因此，正确的相对导入路径是 `..runtime.interfaces`。

这个改动对运行时的功能没有影响，但对静态分析器至关重要，它能精确地表达模块间的真实物理关系，避免了命名空间解析的陷阱。

### 标签

#intent/fix #flow/ready #priority/critical #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将 `fluent.py` 中的绝对导入改为相对导入

我们将修改 `fluent.py`，使用相对路径来导入 `CachePolicy`，从而打破静态分析器发现的命名空间解析循环。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/fluent.py
~~~~~
~~~~~python.old
from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from cascade.spec.runtime.interfaces import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")
~~~~~
~~~~~python.new
from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from ..runtime.interfaces import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")
~~~~~

### 下一步建议

这个改动应该已经解决了所有已知的循环依赖问题。请再次运行 `stitcher check` 进行最终验证。如果检查通过，我们可以将这一系列修复工作合并为一个 `[COMMIT]` 计划。
