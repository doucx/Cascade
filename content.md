You are absolutely right. My previous plan was incomplete and myopic. I correctly refactored the `Call` spec and the *new* compiler in `cascade-compiler`, but I completely failed to account for the *old, legacy* `BlueprintBuilder` located in `packages/cascade-graph/src/cascade/graph/compiler.py`.

The traceback and your `grep` output clearly show my mistake. This legacy file is still being used by parts of the test suite and older execution paths, and it is trying to instantiate the now-purified `Call` object with the `func` keyword argument, causing the `TypeError`.

Thank you for catching this. I will now create a plan to fix this oversight and bring the legacy compiler into alignment with the new specification.

## [WIP] fix(graph): Align legacy BlueprintBuilder with purified Call spec

### 错误分析
上一个计划在从 `cascade.spec.blueprint.Call` 中移除 `func` 字段后，未能更新所有使用该构造函数的地方。具体来说，遗漏了位于 `packages/cascade-graph/src/cascade/graph/compiler.py` 中的旧版 `BlueprintBuilder`。当测试套件加载并尝试使用这个旧编译器时，它试图用一个已经被移除的 `func` 关键字参数来实例化 `Call` 对象，从而导致了 `TypeError`。

### 用户需求
修复因 `Call` spec 变更而导致的 `TypeError`，使整个项目能够再次通过测试。

### 评论
这是一个典型的重构遗漏。在过渡期间，保持遗留代码与更新后的核心规格（spec）兼容是至关重要的。此修复将确保旧的执行路径不会在测试期间崩溃，从而让我们能够继续推进更大范围的架构演进。

### 目标
1.  修改 `packages/cascade-graph/src/cascade/graph/compiler.py`。
2.  从 `Call` 指令的实例化中移除 `func=callable_obj` 参数。

### 基本原理
为了完成对 `Blueprint` 的净化，我们必须确保代码库中没有任何地方再尝试向 `Call` 或 `MapCall` 传递 `func` 参数。此补丁将修复被遗漏的旧编译器，使其符合新的 `Call` 数据契约，从而解决 `TypeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/graph #comp/spec #concept/ir #scope/core #ai/instruct #task/domain/architecture #task/object/ir-model #task/action/refactor #task/state/continue #task/status/active

---

### Script

#### Acts 1: Patch the Legacy `BlueprintBuilder`

我们将修改 `cascade-graph/src/cascade/graph/compiler.py`，移除对 `func` 关键字参数的调用。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/compiler.py
~~~~~
~~~~~python.old
        instr = Call(
            func=callable_obj,
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands,
            task_name=task_name,
            constraints=constraints,
        )
~~~~~
~~~~~python.new
        instr = Call(
            output=output_reg,
            args=args_operands,
            kwargs=kwargs_operands,
            task_name=task_name,
            constraints=constraints,
        )
~~~~~

### 下一步建议
我们已经修复了遗漏的旧编译器。现在，整个代码库应该都与纯化的 `Blueprint` 规范保持一致了。

请再次运行完整的测试套件以确认所有问题都已解决：

`pytest`
