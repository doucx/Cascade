我们已经成功完成了 `ArgumentResolver` 的架构重构，消除了优化路径带来的代码冗余，并确保了 TCO 优先级逻辑在所有场景下的一致性。

## [COMMIT] refactor(engine): 统一 ArgumentResolver 的数据边解析逻辑

### 用户需求
重构 `ArgumentResolver`，消除“快速路径”和“复杂路径”之间重复的数据边解析代码。

### 评论
这是一次重要的高质量重构。通过将核心的“边解析 + 优先级过滤”逻辑提取到私有方法 `_resolve_data_edges` 中，我们不仅消除了重复代码，还显著降低了未来维护的风险。这确保了类似“Jump 优先级高于静态依赖”这样的关键逻辑在整个运行时中只有唯一的事实来源，符合 DRY 原则。

### 目标
1.  提交对 `packages/cascade-engine/src/cascade/runtime/resolvers.py` 的重构，引入 `_resolve_data_edges` 方法。
2.  确保所有 E2E 测试（特别是针对参数覆盖的测试）在重构后依然保持通过。

### 基本原理
采用“提取方法 (Extract Method)”重构技术。将原本分散在两个分支中的、逻辑完全相同的数据边迭代和 `input_overrides` 检查逻辑封装。主解析方法现在作为协调者，根据节点复杂程度选择解析策略，但共享底层的数据提取逻辑。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #scope/core #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交重构变更

我们将重构后的 `resolvers.py` 文件添加到 Git 暂存区并执行提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(engine): unify edge resolution logic in ArgumentResolver

Refactored 'ArgumentResolver' to eliminate code duplication between the
'Fast Path' and 'Complex Path'.

Previously, the logic for iterating over incoming DATA edges and
applying 'input_overrides' (for TCO) was duplicated in two places,
which led to a bug where only one path was correctly updated.

Key changes:
- Introduced '_resolve_data_edges' private method to encapsulate the
  shared logic of dependency resolution and priority filtering.
- Updated both resolution paths to call the unified helper.
- Improved code readability and maintainability by adhering to the
  DRY (Don't Repeat Yourself) principle.

This ensures that the priority of Jump data over static graph
dependencies is consistently enforced across all task types.
~~~~~

### 下一步建议
- **架构审计**: 建议定期审查运行时中其他类似的“快速/慢速”分支，检查是否存在类似的逻辑漂移风险。
- **性能基准测试**: 虽然这次重构提高了代码质量，但引入了一次额外的方法调用。在对性能极度敏感的 TCO 循环中，可以使用 `benchmark` 脚本确认性能损耗在可接受范围内。
