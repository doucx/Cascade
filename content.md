You are absolutely right to keep digging. This is a classic "hydra" problem with dependency cycles; fixing one reveals another. My apologies for not catching this related issue in the same file.

The pattern is identical to the last one. Let's eradicate it.

## [WIP] fix: Resolve circular dependency between spec and execution-graph (Part 3)

### 错误分析

在修复了 `fluent.py` 中对 `interfaces` 的导入后，`stitcher` 又发现了同一个文件 (`fluent.py`) 中的另一个问题。

1.  **路径**: 依赖环路与之前完全相同 (`cli-observer` -> `sdk` -> `spec.dsl.task` -> `spec.dsl.fluent`).
2.  **闭环点**: 环路现在闭合于 `fluent.py` 文件内部的 `with_constraints` 方法中，该方法使用了绝对路径导入 `from cascade.spec.dsl.constraint import ResourceConstraint`。
3.  **根本原因**: 这与上一个问题是同一类错误。`fluent.py` 模块正在尝试导入同一个目录下的兄弟模块 `constraint.py`，但它使用了绝对路径。在复杂的命名空间包环境中，这再次误导了静态分析器，使其重新从顶层 `cascade` 包开始解析，从而触发了循环依赖。

### 用户需求

彻底解决 `stitcher check` 报告的所有循环依赖问题。

### 评论

我们已经确定了根本的模式：在 `cascade-spec` 包内部，必须使用相对导入来引用包内的其他模块，以消除静态分析器的路径解析歧义。`fluent.py` 中 `with_constraints` 方法里的内部导入违反了这一原则。

### 目标

1.  修改 `packages/cascade-spec/src/cascade/spec/dsl/fluent.py` 文件。
2.  定位 `LazyResult.with_constraints` 和 `MappedLazyResult.with_constraints` 两个方法。
3.  将其中的绝对导入 `from cascade.spec.dsl.constraint import ResourceConstraint` 更改为相对导入 `from .constraint import ResourceConstraint`。

### 基本原理

`fluent.py` 和 `constraint.py` 位于同一个 `dsl` 目录中。使用点号 (`.`) 的相对导入 `from .constraint import ...` 是最直接、最无歧-义的方式，它明确指示 Python 解释器和静态分析工具在当前目录查找 `constraint` 模块，从而彻底切断了导致问题的外部解析路径。

### 标签

#intent/fix #flow/ready #priority/critical #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将 `fluent.py` 内部的绝对导入改为相对导入

我们将修改 `LazyResult` 和 `MappedLazyResult` 类中的 `with_constraints` 方法，将内部的绝对导入更改为相对导入。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/fluent.py
~~~~~
~~~~~python.old
    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        # Import internally to avoid circular dependency at module level
        from cascade.spec.dsl.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self
~~~~~
~~~~~python.new
    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        # Import internally to avoid circular dependency at module level
        from .constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/fluent.py
~~~~~
~~~~~python.old
    def with_constraints(self, **kwargs) -> "MappedLazyResult[T]":
        from cascade.spec.dsl.constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self
~~~~~
~~~~~python.new
    def with_constraints(self, **kwargs) -> "MappedLazyResult[T]":
        from .constraint import ResourceConstraint

        self._constraints = ResourceConstraint(requirements=kwargs)
        return self
~~~~~

### 下一步建议

这应该就是这个特定依赖环路的最后一个问题了。请再次运行 `stitcher check`。如果检查通过，请告知我，我将为您创建一个 `[COMMIT]` 计划来将这三次修复作为一个原子提交进行归档。
