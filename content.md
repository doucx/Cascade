This is an excellent catch. We've been peeling an onion, and you've just found the core. The problem isn't in the files we were fixing; they were merely the places where the static analyzer's confusion manifested. The true architectural flaw lies in the `__init__.py` shims themselves.

## [WIP] fix: Dismantle the flawed SDK shim causing import cycles

### 错误分析

我们之前的所有修复都只是在处理症状。`stitcher` 的最新输出终于揭示了问题的根源：

1.  **错误的起点**: 静态分析器为了解析 `cascade.spec.dsl.task`，它首先寻找 `cascade` 这个顶级包。
2.  **命名空间劫持**: 由于 Python 命名空间包的机制，它找到了 `packages/cascade-cli-observer/src/cascade/__init__.py`。
3.  **循环的制造者**: 这个 `__init__.py` 文件立即执行 `from cascade.sdk import *`。
4.  **闭环**: `cascade.sdk` 模块为了提供类型提示，需要导入 `cascade.spec.dsl.task`。这就触发了分析器重新寻找 `cascade` 包，它再次找到了 `cascade-cli-observer` 的 `__init__.py`，从而形成了一个无法解开的**致命循环**。

这个在各个 `cascade` 命名空间提供者包中的 `__init__.py` shim 是一种反模式。它试图通过一个“叶子”包 (`cascade-cli-observer`) 来定义整个命名空间“树干” (`cascade`) 的公共 API，这在静态分析时会造成灾难性的路径解析冲突。

### 用户需求

彻底解决这个顽固的循环依赖问题。

### 评论

**高保真工程公理 (HFEA) 适用**: 这种“为了用户方便”而创建的隐式 API shim 是一种典型的“架构异味”。它破坏了**真理单一来源 (SSoT)** 原则——`cascade.task` 的“真理”来源应该是 `cascade.sdk`，而不应该被 `cascade-cli-observer` 动态地“注入”到顶层命名空间。

**唯一的正确行动是拆除这个产生歧义的魔法**。`cascade.sdk` 才是项目定义的、唯一的公共 API 入口点。其他所有 `__init__.py` 文件都应只负责声明它们是命名空间的一部分，而不应尝试修改该命名空间的内容。

### 目标

1.  定位并修改 `packages/cascade-cli-observer/src/cascade/__init__.py` 文件。
2.  移除其中用于导入和暴露 `cascade.sdk` API 的 shim 代码块。
3.  只保留用于支持命名空间包的 `__path__` 扩展语句。

### 基本原理

通过移除 `__init__.py` 中的 `try...except` 导入块，我们消除了静态分析器在解析 `cascade` 命名空间时遇到的循环陷阱。`cascade-cli-observer` 将不再尝试主动导入 `cascade.sdk`，从而切断了依赖环路。这使得依赖关系变得单向且清晰：任何需要 `task` 或 `LazyResult` 的代码都必须显式地从 `cascade.sdk` 或其源头 (`cascade.spec`) 导入，这才是健康的架构。

### 标签

#intent/refine #flow/ready #priority/critical #comp/build #scope/core #ai/brainstorm #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 移除 `cascade-cli-observer` 中有问题的 SDK Shim

我们将编辑 `__init__.py`，只保留命名空间包所必需的 `__path__` 设置。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python.old
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Shim to expose the SDK API if available in the environment
try:
    from cascade.sdk import *  # noqa: F403
    from cascade.sdk import __all__, __getattr__  # noqa: F401
except ImportError:
    pass
~~~~~
~~~~~python.new
# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议

这个修改应该已经根除了问题的核心。请运行 `stitcher check` 进行验证。

如果检查通过，请告知我，我会立刻生成一个 `[COMMIT]` 计划，将我们这一整个系列的架构修复工作作为一个单一的、有意义的提交进行归档。如果 `stitcher` 发现了其他包（如 `cascade-spec`、`cascade-runtime`）中存在同样的 `__init__.py` shim 问题，我们将以同样的方式修复它们。
