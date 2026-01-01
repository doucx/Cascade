## [WIP] 修复 Pyright 无法解析 `cascade.*` 跨包导入的问题

这是一个典型的 **PEP 420 命名空间包 (Namespace Packages)** 冲突问题。

### 错误分析

在 Cascade 项目中，多个分发包（Distributions）共同贡献于 `cascade.*` 命名空间：
- `cascade-engine` 提供 `cascade.runtime`
- `cascade-graph` 提供 `cascade.graph`
- `cascade-spec` 提供 `cascade.spec`
- ... 以及 `cascade-python` 试图在 `cascade` 顶层提供 `cs.*` Facade API。

**冲突点在于：**
1. `cascade-python` 在 `src/cascade/` 下包含了一个 `__init__.py`（为了定义 `run`, `task`, `Param` 等顶层 API）。
2. 在 Python 中，如果一个命名空间中的某个目录包含了 `__init__.py`，它就会被视为一个**常规包 (Regular Package)**。
3. 如果没有特殊的处理，常规包会“独占”该命名空间，导致 Python（以及 Pyright 等静态分析工具）无法看到其他目录（Implicit Namespace Packages）中贡献的内容。

**解决方案：**
根据 Python 官方建议，当多个包共享同一个顶层命名空间且其中一个包需要 `__init__.py` 时，**所有**参与该命名空间的包都必须在其对应的 `__init__.py` 中显式调用 `pkgutil.extend_path`。

### 用户需求
修复 Pyright 无法解析 `cascade.*` 跨包导入的问题。

### 评论
这是一个架构级的“稳定标识符”问题。为了确保在开发环境（Monorepo）、可编辑安装（Editable Install）以及最终分发中都能保持一致的导入行为，我们需要在所有包的 `cascade` 根目录下建立统一的命名空间声明。

### 目标
1. 在所有缺少的包中创建 `src/cascade/__init__.py`。
2. 在该文件中加入 `pkgutil.extend_path` 样板代码。
3. 确保子命名空间（如 `cascade.providers`, `cascade.connectors`）也具备同样的扩展能力。

### 基本原理
`__path__ = __import__("pkgutil").extend_path(__path__, __name__)` 会告诉 Python 的导入系统：请继续在 `sys.path` 的其他位置寻找同名的包，并把它们的内容合并到当前包的 `__path__` 中。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/config #scope/dx #ai/delegate #task/domain/build-system #task/object/namespace-packages #task/action/standardization #task/state/begin

---

### Script

#### Acts 1: 为所有分发包建立顶层命名空间声明

我们需要在每个子包的 `src/cascade/` 目录下创建一个 `__init__.py`，内容统一为标准的命名空间扩展代码。

~~~~~act
write_file
packages/cascade-engine/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace (like cascade-spec, cascade-graph).
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-common/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-library/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-application/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 规范子命名空间的声明

部分包已经有了子命名空间的声明，但格式不统一。我们将它们规范化。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/connectors/__init__.py
~~~~~
~~~~~python.old
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-connector-mqtt) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~
~~~~~python.new
# This allows 'cascade.connectors' to be a shared namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
1. **重启语言服务器**: 修改 `__init__.py` 后，Pyright 通常需要重启（在 VSCode 中执行 `Pyright: Restart Server`）才能识别新的路径。
2. **验证**: 再次运行 `pyright **/src/**.py`。理论上，除了因为缺少第三方库（如 `redis`, `aiohttp`）导致的错误外，`cascade.*` 内部的导入错误应该全部消失。
3. **环境配置**: 如果 Pyright 仍然报错，可能需要在项目根目录创建一个 `pyrightconfig.json`，并将所有 `packages/*/src` 添加到 `extraPaths` 中。如果你需要，我可以为你生成这个配置文件。
