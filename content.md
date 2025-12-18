简要回答：
这是一个经典的 Python 命名空间遮蔽问题。由于 `cascade-py` 包在 `src/cascade` 下包含了一个 `__init__.py` 文件（为了提供便捷的 API 入口），Python 将其视为一个常规包，从而停止了在其他位置（如 `cascade-interfaces`）查找 `cascade` 子模块的过程。这在 Editable 安装模式下尤为致命。

解决方案是使用 `pkgutil` 扩展 `cascade-py` 的搜索路径，使其表现得像一个命名空间包。

## [WIP] fix(core): 解决 Monorepo 命名空间遮蔽问题

### 用户需求
解决 `ModuleNotFoundError: No module named 'cascade.spec'` 错误。

### 评论
在多包架构中，如果“主包”（`cascade-py`）包含 `__init__.py`，而其他“卫星包”（`cascade-interfaces`）依赖隐式命名空间机制，主包必须显式声明自己扩展路径，否则卫星包在开发模式（Editable Install）下将不可见。

### 目标
在 `cascade-py` 的 `__init__.py` 顶部注入 `pkgutil` 路径扩展代码。

### 基本原理
`__path__ = __import__('pkgutil').extend_path(__path__, __name__)` 是 Python 官方推荐的让包含 `__init__.py` 的包与其他命名空间包共存的标准方法。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #scope/core #ai/instruct #task/domain/core #task/object/namespace #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 注入 pkgutil 路径扩展

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional

# Core Specs
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__('pkgutil').extend_path(__path__, __name__)

import asyncio
from typing import Any, Dict, Optional

# Core Specs
~~~~~

### 下一步建议
修复此问题后，`cascade.spec` 应该可以被正确导入。接下来，我们将不可避免地遇到 `tests/` 目录中大量过时的导入路径（例如测试代码中仍然在使用 `cascade.interfaces.spec`）。建议在下一次交互中批量修复所有测试文件的导入路径。
