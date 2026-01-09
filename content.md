好的，所有静态分析错误已解决。我现在将所有修改文件添加到暂存区并创建一个单独的提交。

## [COMMIT] fix(runtime): Resolve pyright type safety issues in observability and core logic

### 用户需求

确认所有 pyright 静态分析错误已修复，并要求创建一个包含所有这些修复的提交。

### 评论

这次修复确保了 `cascade-runtime` 在使用 `EventState` 枚举和处理 `MapNode` 反序列化时的类型安全。特别是对事件水合逻辑的重构，使其能够更健壮地处理来自 EventIR 的原始数据，彻底解决了 pyright 的类型推断问题。

### 目标

1.  将 `RunFinished` 和 `TaskExecutionFinished` 事件中的硬编码字符串状态（"Succeeded", "Failed"）替换为 `EventState` 枚举成员。
2.  修复 `IRToRuntimeAdapter` 中的序列化逻辑，移除对 `MapNode` 构造函数中已废弃参数的引用。
3.  重构 `_hydrate_lifecycle` 函数，以明确类型和安全的方式处理 `EventState` 的转换，消除 pyright 报告的最后一个类型错误。
4.  创建一个描述性的 Git 提交。

### 基本原理

根据 **高保真工程公理协议 (HFEA)**，我们拒绝平庸且脆弱的实现。使用硬编码字符串作为状态是一种代码异味，因为它无法保证一致性。通过强制使用强类型的 `EventState` 枚举，我们确保了事件流的类型完整性。同时，修复序列化代码中的模型不匹配，保持了代码的架构不可腐蚀性。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #scope/dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 添加所有修改的文件到暂存区

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/graph/serialize.py
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/src/cascade/runtime/legacy/processor.py
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~

#### Acts 2: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime): Resolve pyright type safety issues in observability and core logic

This commit addresses multiple pyright static analysis errors across the runtime package, primarily related to type safety around event handling and graph serialization.

Key fixes:
1. **Type Safety**: Replaced hardcoded status strings ("Succeeded", "Failed") with explicit `EventState` enum members in `Engine.run` and `NodeProcessor.process`.
2. **Serialization**: Removed the obsolete `mapping_factory` parameter from `MapNode` deserialization in `graph/serialize.py` to match the current data model.
3. **Event Hydration**: Refactored `_hydrate_lifecycle` in `observability/events.py` to strictly narrow the type of the incoming state value, satisfying stricter type checking requirements and preventing potential `None` assignment errors.

This ensures the runtime's core components are fully type-safe and consistent with their defined interfaces.
~~~~~

### 下一步建议

`cascade-runtime` 软件包中的 pyright 错误已全部解决并提交。

下一步建议：
1.  **全面测试**: 运行 `packages/cascade-runtime` 的单元测试，以确保这些类型和重构修复没有引入运行时回归。
2.  **下一个任务**: 请提供下一个开发任务或下一个需要检查的软件包。
