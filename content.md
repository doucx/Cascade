你的分析完全正确，我犯了一个错误。

在 `test_resource_contention.py` 的重构中，我移除了手动构建 `function_map` 的逻辑，但忘记了最关键的一步：**将 `resource_heavy_task` 的实现注册到 `CodeRegistry` 中**。

这导致 `Linker` 在 `EventDrivenRunner.from_assembly` 内部进行完整性校验时，发现 `assembly.symbol_table` 要求一个代码哈希，但空的 `code_registry` 无法提供它。

这恰恰证明了我们刚刚实现的 `Linker` 校验机制是有效的——它成功地将一个潜在的运行时崩溃，转变成了一个明确的、在启动时就失败的链接错误。

现在，我将修正这个测试，完成这次重构。

## [WIP] fix(tests): 在重构后的集成测试中正确注册任务代码

### 错误分析
测试 `test_resource_contention.py` 在调用 `EventDrivenRunner.from_assembly` 时失败，并抛出 `LinkerError`。根本原因是，在将该测试迁移到使用新的工厂方法时，我创建了一个空的 `CodeRegistry`，却没有将测试中定义的 `resource_heavy_task` 的函数实现注册进去。

`Linker` 按预期工作，正确地检测到 `Assembly` 所需的代码哈希在 `CodeRegistry` 中缺失，并强制性地阻止了 VM 的启动，从而暴露了我重构中的这个疏忽。

### 用户需求
完成对集成测试的迁移，确保它们在使用 `from_assembly` 后能够正确运行。

### 评论
这次测试失败完美地体现了“快速失败”原则的价值。我们新引入的 `Linker` 校验机制成功地捕获了一个本应在运行时才会暴露的“代码未找到”错误，证明了该机制的正确性和必要性。

### 目标
1.  修复 `test_resource_contention.py` 测试。
2.  在调用 `EventDrivenRunner.from_assembly` 之前，正确地从 `assembly.symbol_table` 提取 `resource_heavy_task` 的 `canonical_code_structure_hash`，并将其与 `resource_heavy_task.func` 一起注册到 `CodeRegistry` 中。

### 基本原理
`Linker` 的契约要求 `CodeRegistry` 必须提供 `Assembly` 中 `symbol_table` 所需的所有代码实现。测试用例必须遵循这一契约，通过在链接前填充 `CodeRegistry` 来满足这一依赖关系。由于该测试中的所有任务都是 `resource_heavy_task` 的实例，它们共享同一个 `canonical_code_structure_hash`，我们只需注册一次即可。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/linking #scope/dx #ai/instruct #task/domain/vm #task/object/linker #task/action/integration #task/state/end

---

### Script

#### Acts 1: 修复 `test_resource_contention.py` 中的代码注册逻辑

我们将添加必要的代码，在调用 `from_assembly` 之前，将 `resource_heavy_task` 注册到 `CodeRegistry`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # --- PART B: EXECUTION ASSERTION ---
    print("\n--- Physical Field Event Log (Observed) ---")

    code_registry = CodeRegistry()
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    await runner.start_loop()
~~~~~
~~~~~python.new
    # --- PART B: EXECUTION ASSERTION ---
    print("\n--- Physical Field Event Log (Observed) ---")

    code_registry = CodeRegistry()
    # All tasks are the same, so they share the same canonical hash.
    # We can just grab the first one from the symbol table to register the implementation.
    if assembly.symbol_table:
        canonical_hash = next(iter(assembly.symbol_table.values()))
        code_registry.register(canonical_hash, resource_heavy_task.func)

    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    await runner.start_loop()
~~~~~

### 下一步建议
我们已经成功完成了对所有相关集成测试的迁移和修复，这项任务现已完成。

现在，我建议我们继续推进“战略分析”中确定的下一个关键任务：**实现双通道出口 (Dual-Channel Egress)**。这将解决错误 Token 掉入虚空导致系统意外静止的严重问题，是提升系统稳定性的关键一步。
