好的，我理解了问题。`pyright` 在分析 `cascade-python` 包时，无法找到那些实际上位于 `cascade-sdk` 包中的模块（如 `control_flow`, `testing`, `tools.cli`, `providers.registry`），尽管它们在运行时会共享同一个 `cascade` 命名空间。

这是一种典型的在使用命名空间包 (namespace packages) 的 monorepo 结构中遇到的静态分析挑战。最直接且正确的解决方法是告知 `pyright` 在这些特定位置忽略缺失的导入，因为我们知道在完整的环境下这些导入是有效的。

我将生成一个计划，通过添加 `# type: ignore` 注释来精确地解决这四个导入错误。

## [WIP] fix: 解决 cascade-python 中的 pyright 导入错误

### 错误分析

用户提供的 `pyright` 输出指出了四个 `reportMissingImports` 错误。根本原因在于项目的 monorepo 结构：
1.  `cascade-python` 和 `cascade-sdk` 是两个独立的包，但它们共同构成了 `cascade` 这个命名空间。
2.  `cascade-python` 包的根 `__init__.py` 文件扮演了一个“外观”(Facade) 的角色，它尝试从整个 `cascade` 命名空间（包括 `cascade-sdk` 中定义的模块）导出符号。
3.  当 `pyright` 单独分析 `cascade-python` 的源代码树时，它无法看到 `cascade-sdk` 中的文件，因此认为 `cascade.control_flow`, `cascade.testing` 等模块不存在，从而报告导入错误。

### 用户需求

解决 `pyright packages/cascade-python/` 命令报告的所有四个 `reportMissingImports` 错误，使静态分析能够通过。

### 评论

这是一个在复杂 Python 项目中很常见的静态分析配置问题。直接修改代码结构或移动文件是过度设计且不必要的。采用 `# type: ignore [reportMissingImports]` 注释是解决此类问题的标准实践，因为它可以在不影响运行时逻辑的情况下，为静态分析工具提供足够的信息以消除误报。

### 目标

1.  为 `cascade.control_flow` 的导入添加 `type: ignore` 注释。
2.  为 `cascade.testing` 的导入添加 `type: ignore` 注释。
3.  为 `cascade.tools.cli` 的导入添加 `type: ignore` 注释。
4.  为 `cascade.providers.registry` 的导入添加 `type: ignore` 注释。

### 基本原理

我们将使用四个独立的、原子化的 `patch_file` 操作来修改 `packages/cascade-python/src/cascade/__init__.py` 文件。这种方法确保了每个改动都精确地针对一个错误，使得计划清晰、易于审查，并降低了引入错误的风险。

### 标签

#intent/fix #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/static-analysis #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 `TYPE_CHECKING` 块内的导入错误

我们将逐一为在 `if TYPE_CHECKING:` 块内引发错误的三个导入语句添加忽略指令。

首先是 `control_flow`。
~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    from cascade.control_flow import select_jump, bind
~~~~~
~~~~~python.new
    from cascade.control_flow import select_jump, bind  # type: ignore [reportMissingImports]
~~~~~

其次是 `testing`。
~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    from cascade.testing import override_resource, ControllerTestApp
~~~~~
~~~~~python.new
    from cascade.testing import override_resource, ControllerTestApp  # type: ignore [reportMissingImports]
~~~~~

最后是 `tools.cli`。
~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    from cascade.tools.cli import create_cli
~~~~~
~~~~~python.new
    from cascade.tools.cli import create_cli  # type: ignore [reportMissingImports]
~~~~~

#### Acts 2: 修正 `__getattr__` 内的导入错误

现在，我们修正 `__getattr__` 函数内部对 `providers.registry` 的动态导入。
~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
    try:
        from cascade.providers.registry import registry

        return registry.get(name)
    except (ImportError, AttributeError):
~~~~~
~~~~~python.new
    try:
        from cascade.providers.registry import registry  # type: ignore [reportMissingImports]

        return registry.get(name)
    except (ImportError, AttributeError):
~~~~~
