Excellent catch. Your analysis is spot on. The traceback clearly indicates a `TypeError` because I attempted to instantiate a type alias (`SymbolTable`, which is `typing.Dict`) instead of using the proper constructor for an empty dictionary (`dict()`). This is a classic mistake when mixing type hints and runtime code.

I will now generate a plan to correct this error and get our test back on track.

## [WIP] fix(tests): Correct SymbolTable instantiation in retry topology test

### 错误分析

测试 `test_retry_topology.py` 失败，并伴有 `TypeError: Type Dict cannot be instantiated; use dict() instead` 的 traceback。

根本原因是在 `retry_harness` fixture 中，我们错误地使用了类型别名 `SymbolTable` (`typing.Dict[str, str]`) 作为构造函数来创建一个空的 `symbol_table`。在 Python 中，`typing` 模块中的泛型类型别名不能被直接实例化。创建一个空字典的正确方法是使用 `dict()` 或 `{}`。

### 用户需求

修复在 `F_retry` 节点集成测试中因 `SymbolTable` 实例化不正确而导致的 `TypeError`，使测试能够正常运行。

### 评论

这是一个简单但关键的修复。它暴露了在代码中区分类型定义和可实例化对象的重要性。修正这个问题将使我们能够继续 TDD 流程，确保 `F_retry` 节点在我们将其集成到编译器之前是完全可靠的。

### 目标

1.  定位 `packages/cascade-vm/tests/integration/test_retry_topology.py` 文件中错误的 `SymbolTable()` 调用。
2.  将其替换为正确的空字典构造函数 `dict()`。

### 基本原理

我们将直接修正导致 `TypeError` 的代码行。通过将 `SymbolTable()` 更改为 `dict()`，我们提供了 `Assembly` 数据类所期望的正确类型的、可运行的实例（一个空的字典），从而解决类型错误并使测试能够继续执行。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/vm #scope/dx #ai/instruct #task/domain/core #task/object/retry-node #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `SymbolTable` 的实例化

我们将修补 `test_retry_topology.py` 文件，以正确的方式创建一个空的符号表。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_retry_topology.py
~~~~~
~~~~~python.old
    assembly = Assembly(graph=graph, symbol_table=SymbolTable())
    # The runner's linker will automatically map the RetryNode type to its implementation
    runner = EventDrivenRunner.from_assembly(assembly, CodeRegistry())
    runner.prime()
~~~~~
~~~~~python.new
    assembly = Assembly(graph=graph, symbol_table=dict())
    # The runner's linker will automatically map the RetryNode type to its implementation
    runner = EventDrivenRunner.from_assembly(assembly, CodeRegistry())
    runner.prime()
~~~~~

### 下一步建议

这个修复应该能解决当前的 `TypeError` 并让测试套件通过。一旦测试通过，我们就验证了 `F_retry` 节点在物理层的行为是正确的。

接下来，我们应该回到之前的轨道上：**开始实施将 `LazyResult.with_retry()` 用户意图编译成使用 `F_retry` 节点的物理拓扑的编译器布线策略**。
