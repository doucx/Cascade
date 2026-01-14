You've hit the jackpot. Your investigation has revealed the true, systemic nature of the architectural flaw. This isn't a localized issue; it's a project-wide anti-pattern. Thank you for providing the complete picture. It's time to perform a foundational refactoring.

## [WIP] refactor: Systemically remove flawed SDK shims from all `__init__.py` files

### 错误分析

用户提供的文件列表证实，之前的问题并非个例，而是一个在所有 `cascade` 命名空间包中被复制的、有缺陷的设计模式。

每一个 `packages/*/src/cascade/__init__.py` 文件都包含了一个“SDK shim”，它尝试将 `cascade.sdk` 的内容动态注入到顶层 `cascade` 命名空间。

这导致了以下致命问题：
1.  **命名空间劫持**: 任何一个包含此 shim 的包，在静态分析时都有可能被错误地识别为 `cascade` 命名空间的“根”。
2.  **强制循环依赖**: 当分析器（错误地）从例如 `cascade-compiler` 开始解析 `cascade` 时，其 `__init__.py` 会立即导入 `cascade.sdk`。而 `cascade.sdk` 为了提供类型提示，又需要导入 `cascade.spec`。当分析器解析 `cascade.spec` 时，它再次从顶层查找 `cascade`，又可能找到另一个包（比如 `cascade-cli-observer`），从而陷入一个无法解析的循环。

这个模式，虽然可能是为了简化用户的导入语句（`import cascade as cs; cs.task`），但它以牺牲架构的清晰性、稳定性和工具兼容性为代价，是不可接受的。

### 用户需求

用户已经识别出这个有问题的 shim 遍布于整个代码库，并要求进行系统性的修复。

### 评论

**根据高保真工程公理 (HFEA)，此架构异味必须被彻底根除。**

这种隐式的、神奇的 API 暴露方式严重违反了**真理单一来源 (SSoT)**原则。`cascade` 公共 API 的唯一真理来源应该是 `cascade.sdk` 模块本身。通过在所有包的 `__init__.py` 中复制这个 shim，我们创造了十几个潜在的、相互冲突的“真理来源”，这使得静态分析和依赖管理变得不可能。

正确的做法是拆除所有这些 shim。开发者和用户应该显式地从 `cascade.sdk` 导入他们需要的功能（例如 `from cascade.sdk import task`）。这遵循了 Python 的“显式优于隐式”原则，并恢复了架构的确定性。

### 目标

1.  定位 Monorepo 中所有 `packages/*/src/cascade/__init__.py` 文件。
2.  从所有这些文件中移除 SDK 导入 shim (`try...except` 块)。
3.  确保这些 `__init__.py` 文件中只保留用于支持命名空间包的 `__path__ = ...` 语句。

### 基本原理

通过对所有相关的 `__init__.py` 文件进行清理，我们消除了所有可能导致静态分析器混淆的路径。这将使项目的依赖关系图变得清晰、单向且无环。任何模块对 `cascade` API 的需求都将通过一个唯一的、确定的路径——`cascade.sdk`——来满足，从而彻底解决这个顽固的循环依赖问题。

### 标签

#intent/refine #flow/ready #priority/critical #comp/build #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 在整个项目中系统性地清除 SDK Shim

我将为用户提供的列表中的每一个 `__init__.py` 文件生成一个 `patch_file` 操作，以移除有问题的代码。

~~~~~act
write_file
packages/cascade-application/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
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
packages/cascade-compiler/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-connector-local/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-execution-graph/src/cascade/__init__.py
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
packages/cascade-provider-ipfs/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-reflection/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-sdk/src/cascade/__init__.py
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
packages/cascade-std/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-vm/src/cascade/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
# that contribute to the 'cascade' namespace.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议

我们已经对所有已知的 `__init__.py` 文件应用了修复。这应该已经彻底解决了循环依赖的根源。

请运行 `stitcher check` 进行最终确认。如果检查通过，请告诉我，我将为您创建一个 `[COMMIT]` 计划，将这项重要的架构重构工作正式提交。
