You are absolutely right. I apologize for that oversight. In my previous attempt to defensively fix a potential variable scope issue, I renamed the variable to `raw_func` but failed to update its final usage, leading directly to this `NameError`.

I will now generate a `[WIP]` plan to correct this specific error immediately.

## [WIP] fix(compiler): Correct variable name in frontend to fix NameError

### 错误分析
如您所指出的，在 `frontend.py` 中，我引入了变量 `raw_func` 以替代 `func`，但在最后一步向 `symbol_table` 赋值时，错误地保留了对已不存在的变量 `func` 的引用，导致了 `NameError`。

### 用户需求
修复 `frontend.py` 中的 `NameError`，确保 `symbol_table` 被正确填充。

### 评论
这是一个简单的重构错误。我将立即修正这个变量名，以完成我上一步未竟的修复。

### 目标
1.  将 `frontend.py` 中对未定义变量 `func` 的引用更正为 `raw_func`。
2.  确保 `MappedLazyResult` 的编译流程无 `NameError`。

### 基本原理
通过一个精确的 `patch_file` 操作，替换掉错误的代码行，将变量名对齐，从而解决 `NameError`。

### 标签
#intent/fix #flow/ready #priority/high
#comp/compiler #concept/parser
#ai/instruct
#task/domain/architecture #task/object/identity-hash #task/action/enforce
#task/state/continue

---

### Script

#### Acts 1: 修正 `frontend.py` 中的变量名错误

我们将精确定位到 `_visit_mapped_result` 方法中错误的代码块，并将其中的 `func` 替换为正确的 `raw_func`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        # Ensure we store the raw function, not the Task wrapper
        raw_func = obj.factory
        if hasattr(raw_func, "func"):  # Unwrap Task objects
            raw_func = raw_func.func

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = raw_func
        self.symbol_table[task_def.canonical_code_structure_hash] = func
~~~~~
~~~~~python.new
        # Ensure we store the raw function, not the Task wrapper
        raw_func = obj.factory
        if hasattr(raw_func, "func"):  # Unwrap Task objects
            raw_func = raw_func.func

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = raw_func
~~~~~

### 下一步建议
这次修复非常精确，旨在解决您发现的 `NameError`。执行此计划后，请重新运行测试。我们应该会看到 `test_compile_map_node` 的失败消失，并且 `cascade-compiler` 相关的其他 `TypeError` 依然存在，这符合我们的预期，因为它们是我上一个计划中其他步骤的目标。
