## [WIP] fix: 修复 cascade-provider-ipfs 缺失的命名空间声明

### 错误分析
`AttributeError: module 'cascade' has no attribute 'ipfs'` 表明 `cascade.sdk` 已经成功加载（因为错误信息来自 `sdk.py` 的 `__getattr__`），但无法通过 `registry.get("ipfs")` 找到 IPFS 提供者。

这通常是因为 `cascade-provider-ipfs` 包未能正确注册其 Entry Points，或者其代码无法被加载。
检查文件结构发现，`packages/cascade-provider-ipfs/src/cascade/` 目录下缺失 `__init__.py` 文件。
在 Python 的 `pkgutil` 风格命名空间包中，所有参与该命名空间的发行版（Distribution）都必须在对应目录包含一个执行 `pkgutil.extend_path` 的 `__init__.py`。缺失此文件导致 `cascade-provider-ipfs` 无法将其 `src/cascade` 目录合并到 `cascade` 命名空间中，进而导致 `cascade.providers.ipfs` 无法被导入，Entry Point 加载失败。

### 用户需求
修复 IPFS 提供者无法加载的问题，确保 `import cascade` 后能通过 `cs.ipfs` 访问相关功能。

### 评论
除了修复缺失的文件，我也会将“垫片（Shim）”代码应用到 `cascade-library` 和 `cascade-common`，以增强系统在不同安装顺序下的健壮性。

### 目标
1. 创建 `packages/cascade-provider-ipfs/src/cascade/__init__.py`。
2. 确保 `packages/cascade-provider-ipfs/src/cascade/providers/__init__.py` 正确配置。
3. 为 `cascade-library` 和 `cascade-common` 添加 API 垫片。

### 基本原理
命名空间包的每一层级目录（如果是跨包共享的）都必须包含 `pkgutil` 声明。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/namespace-package #scope/core #ai/instruct #task/domain/build #task/object/namespace-package #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 为 cascade-provider-ipfs 创建顶层 __init__.py
这是修复当前错误的关键步骤。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/__init__.py
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

#### Acts 2: 确保 cascade-provider-ipfs 的 providers 子包也是命名空间
为了安全起见，重写 `providers/__init__.py` 以确保它也使用了 `pkgutil`，因为 `cascade.providers` 也是一个跨包共享的命名空间。

~~~~~act
write_file
packages/cascade-provider-ipfs/src/cascade/providers/__init__.py
~~~~~
~~~~~python
# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 3: 为 cascade-library 添加 Shim
`cascade-library` 是核心依赖，很容易被第一个加载。

~~~~~act
write_file
packages/cascade-library/src/cascade/__init__.py
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

#### Acts 4: 为 cascade-common 添加 Shim
同理，增强 `cascade-common` 的健壮性。

~~~~~act
write_file
packages/cascade-common/src/cascade/__init__.py
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

#### Acts 5: 为 cascade-engine 添加 Shim
`cascade-engine` 也是一个可能的入口点。

~~~~~act
write_file
packages/cascade-engine/src/cascade/__init__.py
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
