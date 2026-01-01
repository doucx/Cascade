Excellent catch. You've uncovered a subtle but critical bug that my previous refactoring missed. The test failure clearly indicates that the way the `cs.Env` factory function constructs the underlying task call is not aligned with the test's expectations, leading to an incorrect graph structure.

My apologies for this oversight. I will correct it now.

## [WIP] fix: Use keyword argument in Env factory to ensure correct graph binding

### 錯誤分析
测试 `test_build_graph_with_env_factory` 失败的根本原因是 `cs.Env` 工厂函数在调用底层的 `_get_env_var` 任务时，使用了**位置参数** (`_get_env_var("HOME")`) 而不是**关键字参数** (`_get_env_var(name="HOME")`)。

1.  **GraphBuilder 的行为**: `GraphBuilder` 忠实地反映了 `LazyResult` 的内部结构。当它看到一个位置参数时，它会生成 `input_bindings` 为 `{'0': 'HOME'}`，其中 `'0'` 代表第一个参数的索引。
2.  **测试的期望**: 测试用例期望图节点能明确反映出参数的 *名称*，即 `{'name': 'HOME'}`。这是一种更健壮、更具可读性的图表示法。
3.  **问题的根源**: 位于 `packages/cascade-python/src/cascade/__init__.py` 中的 `Env` 工厂函数是造成这种不匹配的源头。

### 用户需求
修复 `test_build_graph_with_env_factory` 测试失败的问题，确保 `cs.Env` 生成的图节点具有正确的、基于名称的输入绑定。

### 评论
这是一个很好的修正。通过在工厂函数中使用关键字参数，我们让生成的计算图更加明确和自文档化。这不仅能修复测试，还能提高整个图表示的健壮性，使其不受函数签名中参数顺序变化的影响。

### 目标
1.  修改 `packages/cascade-python/src/cascade/__init__.py` 文件中的 `Env` 工厂函数。
2.  将对 `_get_env_var` 的调用从 `_get_env_var(name)` 更改为 `_get_env_var(name=name)`。

### 基本原理
通过显式使用关键字参数 `name=name` 来调用 `_get_env_var` 任务，`LazyResult` 对象内部将记录 `kwargs={'name': ...}` 而不是 `args=(...,)`。因此，`GraphBuilder` 在处理这个 `LazyResult` 时，会正确地生成 `input_bindings={'name': 'HOME'}`，从而满足测试断言的要求。

### 标签
#intent/fix #flow/ready #priority/high #comp/sdk #comp/graph #comp/tests #scope/core #ai/instruct #task/domain/build #task/object/circular-dependency #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 `Env` 工厂函数的调用方式

我将精确定位到 `cascade-python` 的 `__init__.py` 文件，并修改 `Env` 工厂函数，使其使用关键字参数来调用底层任务。

~~~~~act
patch_file
packages/cascade-python/src/cascade/__init__.py
~~~~~
~~~~~python.old
def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.context import get_current_context
    from cascade.common.inputs import _get_env_var

    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name)
~~~~~
~~~~~python.new
def Env(name: str, default: Any = None, description: str = "") -> "LazyResult":
    from cascade.spec.input import EnvSpec
    from cascade.context import get_current_context
    from cascade.common.inputs import _get_env_var

    spec = EnvSpec(name=name, default=default, description=description)
    get_current_context().register(spec)
    return _get_env_var(name=name)
~~~~~

### 下一步建议
我们已经完成了对循环依赖问题的修复及其所有连锁效应。现在代码库的底层架构应该是稳定和正确的了。

接下来，我强烈建议我们回到最初计划的第二步：**为 `cascade-python` 添加 `__init__.pyi` 类型存根文件**。这将解决 Pyright 报告中大量的 `reportAttributeAccessIssue` 错误，并为使用 Cascade SDK 的开发者提供急需的 IDE 自动补全和类型检查支持。

如果你同意，我将为此生成计划。
