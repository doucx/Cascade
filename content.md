太棒了。既然测试已经验证了路径重构的正确性，我们现在可以将这些变更正式提交到版本库中。

## [COMMIT] refactor(spec): Relocate execution strategy interfaces to `cascade-spec`

### 用户需求
完成 `ExecutionContext` 和 `ExecutionStrategy` 从 `cascade-runtime` 到 `cascade-spec` 的迁移工作并提交。

### 评论
这次重构强化了 `cascade-spec` 作为系统“规范层”的角色。通过将策略契约下沉，我们为未来可能的多种运行时实现（如不同语言或不同并发模型的实现）奠定了统一的接口基础。

### 目标
1.  将受影响的文件添加到 Git 暂存区。
2.  创建一个清晰、符合 Conventional Commits 规范的提交记录。

### 基本原理
根据 `d3-constraint-quipu-plan-script-rules`，文件修改和 Git 提交必须分步进行。当前计划仅负责执行 Git 操作。

### 标签
#intent/refine #flow/ready #priority/medium #comp/spec #comp/runtime #concept/interfaces #scope/api #ai/instruct #task/domain/architecture #task/object/strategies-interface #task/action/move #task/state/end

---

### Script

#### Acts 1: 提交接口迁移变更

我们将迁移后的新文件、修改后的导出文件以及更新了导入路径的运行时文件一并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
packages/cascade-spec/src/cascade/spec/runtime/__init__.py
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/__init__.py
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/graph.py
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(spec): relocate execution strategy interfaces to cascade-spec

Relocates 'ExecutionContext' and 'ExecutionStrategy' from 'cascade-runtime' to 'cascade-spec' to unify the runtime specification layer.

Key changes:
1. Moved 'base.py' from 'cascade.runtime.legacy.strategies' to 'cascade.spec.runtime.strategies'.
2. Updated 'cascade.spec.runtime' to export these core interfaces.
3. Updated 'Engine', 'GraphExecutionStrategy', and 'VMExecutionStrategy' in 'cascade-runtime' to use the new spec-based import paths.

This move ensures that the core contract between the Engine and its execution strategies is defined in the specification package, enabling better decoupling and facilitating future multi-language or multi-model strategy implementations.
~~~~~

### 下一步建议
接口迁移完成后，我们的 `cascade-spec` 变得更加完备。考虑到我们在 `strategies.py` 中定义了 `ExecutionContext`，我建议接下来审查一下 `cascade-vm` 的物理执行流程，看看是否可以利用这些标准接口来进一步规范 `Reactor` 的运行上下文注入逻辑。
