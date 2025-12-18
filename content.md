简要回答：
遗留的子模块（特别是 `providers` 和 `internal` 目录）中仍包含旧的导入路径。

# [PASS]

## [WIP] fix(core): 批量修复子模块中的遗留导入路径

### 用户需求
解决运行 `pytest` 时出现的 `ModuleNotFoundError: No module named 'cascade.interfaces.spec'` 错误。

### 评论
虽然顶层入口文件已修复，但 `cascade-py` 的 `internal` 和 `providers` 子目录，以及 `cascade-runtime` 的部分核心逻辑中仍大量存在指向旧路径（如 `cascade.interfaces.spec` 和 `cascade.runtime.protocols`）的引用。这需要一次彻底的扫除。

### 目标
1.  修正 `cascade-py` 中 `internal` 和 `providers` 目录下所有文件的导入路径。
2.  修正 `cascade-runtime` 中遗漏的 `cascade.runtime.protocols` 引用。

### 基本原理
将所有 `cascade.interfaces.spec.*` 统一替换为 `cascade.spec.*`，将所有 `cascade.runtime.protocols` 统一替换为 `cascade.interfaces.protocols`。

### 标签
#intent/fix #flow/ready #priority/high #comp/core #scope/core #ai/instruct #task/domain/core #task/object/monorepo #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `internal` 模块

~~~~~act
patch_file
packages/cascade-py/src/cascade/internal/inputs.py
~~~~~
~~~~~python
import os
from typing import Any, Dict, Optional
from cascade.interfaces.spec.task import task

# 这个任务的职责是从 Engine 提供的参数上下文中获取值。
~~~~~
~~~~~python
import os
from typing import Any, Dict, Optional
from cascade.spec.task import task

# 这个任务的职责是从 Engine 提供的参数上下文中获取值。
~~~~~

#### Acts 2: 批量修复 `providers` 模块

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/http.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any, Dict, Optional
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any, Dict, Optional
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/io.py
~~~~~
~~~~~python
import asyncio
import os
from typing import Any, Union
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~
~~~~~python
import asyncio
import os
from typing import Any, Union
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/s3.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Optional
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~
~~~~~python
import asyncio
from typing import Any, Optional
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/shell.py
~~~~~
~~~~~python
import asyncio
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory
~~~~~
~~~~~python
import asyncio
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/sql.py
~~~~~
~~~~~python
except ImportError:
    sqlalchemy = None

from cascade.interfaces.spec.task import task, LazyResult
from cascade.interfaces.spec.resource import inject
from cascade.providers import LazyFactory
~~~~~
~~~~~python
except ImportError:
    sqlalchemy = None

from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
from cascade.providers import LazyFactory
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/stdio.py
~~~~~
~~~~~python
import sys
import asyncio
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~
~~~~~python
import sys
import asyncio
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/template.py
~~~~~
~~~~~python
from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory
~~~~~
~~~~~python
from cascade.spec.task import task
from cascade.providers import LazyFactory
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/config.py
~~~~~
~~~~~python
except ImportError:
    yaml = None

from cascade.interfaces.spec.task import task
from cascade.providers import LazyFactory, Provider
import asyncio
~~~~~
~~~~~python
except ImportError:
    yaml = None

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
import asyncio
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/providers/subflow.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
from cascade.runtime.engine import Engine
~~~~~
~~~~~python
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
from cascade.runtime.engine import Engine
~~~~~

#### Acts 3: 修复 `runtime` 中遗漏的 Protocols 引用

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend


class FlowManager:
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.interfaces.protocols import StateBackend


class FlowManager:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend


class ArgumentResolver:
~~~~~
~~~~~python
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.interfaces.protocols import StateBackend


class ArgumentResolver:
~~~~~

### 下一步建议
核心库代码的修复应该已经完成了。再次运行 `pytest`，预计错误将转移到 `tests/` 目录中的测试文件上，因为我们尚未更新那些文件中的导入路径。接下来的步骤是批量修复 `tests/` 目录。
