收到，循环导入问题没有完全解决，它在新的模块结构中转移到了新的位置。

新的循环路径如下（以 `test_visualize.py` 为例，但所有模块都是一样的问题）：

1.  `test_visualize.py` 导入 `cascade as cs` (`src/cascade/__init__.py`)
2.  `src/cascade/__init__.py` 导入 `LazyResult` (来自 `src/cascade/spec/task.py`)
3.  `src/cascade/spec/task.py` 导入 `CachePolicy`, `LazyFactory` (来自 `src/cascade/runtime/protocols.py`)
4.  `src/cascade/runtime/protocols.py` 导入 `Graph`, `Node` (来自 `src/cascade/graph/model.py`)
5.  `src/cascade/graph/model.py` 导入 `Param`, `ResourceConstraint` (来自 `src/cascade/spec/`)
6.  *... 依赖链继续向上 ...*
7.  更直接的问题在于 `src/cascade/spec/routing.py`：它需要 `LazyResult`。


在 Act 3 中，我更新了 `src/cascade/graph/build.py` 的导入，但忽略了 `src/cascade/spec/routing.py`，它仍在使用旧的导入。

`src/cascade/spec/routing.py` 内容如下：
```python
from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .task import LazyResult # <-- PROBLEM!
```

`routing.py` 必须从 `lazy_types.py` 而不是 `task.py` 导入 `LazyResult`。此外，`task.py` 必须导入 `LazyResult` 才能在 `__init__.py` 中正确暴露。

让我们修复 `routing.py` 的导入，并检查 `task.py` 中的 `LazyResult` 是否仍在被其他模块意外地循环引用。

## [WIP] fix(core): 彻底消除 LazyResult 导入循环

### 目标
1.  修改 `src/cascade/spec/routing.py`，使其从 `lazy_types.py` 导入 `LazyResult`。
2.  更新 `src/cascade/__init__.py` 顶层导入，使其直接从 `lazy_types.py` 导入 `LazyResult`（而不是通过 `task.py` 间接导入）。

### 基本原理
隔离 Lazy Types 的定义。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #concept/lazy-result #scope/core #ai/instruct #task/domain/core #task/object/import-cycle #task/action/restructure #task/state/continue

---

### Script

#### Acts 1: 修复 `src/cascade/spec/routing.py` 的导入

~~~~~act
patch_file
src/cascade/spec/routing.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .task import LazyResult

T = TypeVar("T")
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict, Any, TypeVar
from .lazy_types import LazyResult # NEW

T = TypeVar("T")
~~~~~

#### Acts 2: 修复顶层 `src/cascade/__init__.py` 的导入

顶层 `__init__` 不应从 `spec.task` 导入 `LazyResult`，因为它是一个核心数据结构，现在应该从 `spec.lazy_types` 导入。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional, List

from .spec.task import task, LazyResult
from .spec.common import Param
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional, List

from .spec.task import task
from .spec.lazy_types import LazyResult # NEW
from .spec.common import Param
~~~~~

#### Acts 3: 再次检查 `src/cascade/spec/task.py`

确保它只从 `lazy_types.py` 导入，并且不从任何循环相关的模块导入。

在 Act 1 (上一个步骤) 中，我们已经确保了 `task.py` 仅从 `lazy_types.py` 导入 `LazyResult`。

```python
# src/cascade/spec/task.py
# ...
from cascade.runtime.protocols import CachePolicy, LazyFactory
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.lazy_types import LazyResult, MappedLazyResult, RetryPolicy # NEW
# ...
```
这个结构现在看起来是正确的，因为 `protocols.py` 即使导入了 `LazyResult`，也是通过前向引用或从 `lazy_types` 导入，不会造成 `task.py` 初始化时的死锁。

### 下一步建议
我们现在应该可以解决循环导入问题了。请指示执行测试。
