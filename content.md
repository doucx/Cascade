## [WIP] fix: 全面应用命名空间垫片并清理重复模块

### 错误分析
`AttributeError: module 'cascade' has no attribute 'ipfs'` 问题的根本原因在于 Python 命名空间包的加载机制。当多个包共享 `cascade` 命名空间时，Python 只会执行第一个被加载的 `__init__.py`。如果这个“获胜”的 `__init__.py` 没有包含 API 暴露逻辑（即“垫片/Shim”），那么 `import cascade` 将得到一个空模块，导致后续的 `cs.ipfs` 或 `cs.task` 调用失败。

虽然之前已经修复了核心包，但 `cascade-cli-controller`、`cascade-connector-mqtt` 等其他包也拥有顶层的 `cascade/__init__.py` 且尚未包含垫片。如果测试环境的 `sys.path` 恰好让这些包先被加载，就会重现上述错误。

此外，发现 `cascade-sdk` 和 `cascade-library` 中存在重复的 `cascade.providers.registry` 和 `manager` 模块。这种重复会导致“幽灵行为”，即修改了其中一个文件但系统使用的是另一个，必须清理。

### 用户需求
彻底修复 `import cascade` 时的属性丢失问题，确保无论安装了哪些 Cascade 包，都能正确访问 SDK API 和 Provider。

### 评论
这是一个系统性的架构修复。通过在所有发行版的 `cascade/__init__.py` 中统一应用垫片，我们消除了加载顺序带来的不确定性。同时清理重复代码也是维护大型 Monorepo 的必要步骤。

### 目标
1. 从 `cascade-sdk` 中删除重复的 Provider 管理代码 (`manager.py`, `registry.py`)，统一使用 `cascade-library` 中的版本。
2. 为剩余的所有 Cascade 包 (`cli`, `connector`, `graph`) 的 `cascade/__init__.py` 添加 SDK 垫片。
3. 重新确认 `cascade-provider-ipfs` 的子包结构正确。

### 基本原理
1.  **单一事实来源 (SSOT)**: 代码不应重复。
2.  **防御性命名空间**: 任何参与命名空间的 `__init__.py` 都必须具备完整的初始化能力。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/namespace-package #scope/core #ai/instruct #task/domain/build #task/object/namespace-package #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 清理 cascade-sdk 中的重复模块
删除 `cascade-sdk` 中的 `manager.py` 和 `registry.py`，因为它们已经存在于 `cascade-library` 中，且 `sdk` 依赖 `library`。保留 `__init__.py` 以维持命名空间。

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/providers/manager.py
~~~~~

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/providers/registry.py
~~~~~

#### Acts 2: 为 cascade-cli-controller 添加 Shim
~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~

#### Acts 3: 为 cascade-cli-observer 添加 Shim
~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~

#### Acts 4: 为 cascade-connector-local 添加 Shim
~~~~~act
write_file
packages/cascade-connector-local/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~

#### Acts 5: 为 cascade-connector-mqtt 添加 Shim
~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~

#### Acts 6: 为 cascade-graph 添加 Shim
~~~~~act
write_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *
    from cascade.sdk import __all__, __getattr__
except ImportError:
    pass
~~~~~

#### Acts 7: 再次确认 cascade-provider-ipfs 的 providers 子包
确保这个文件存在且正确，以防上次操作未生效或被覆盖。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/__init__.py
~~~~~
~~~~~python
# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~
