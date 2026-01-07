好的，既然所有测试都已顺利通过，这证明我们的重构已经完美闭合，实现了从事件生产者到最终消费者的端到端类型安全。

我将生成一个 `[COMMIT]` 计划，将这一重要的架构演进记录到代码库中。

## [COMMIT] refactor(events): Unify event state contract to use EventState enum

### 错误分析

系统中存在深层级的“语义漂移” (Semantic Drift)：
- **生产者** (`Stainer`) 使用 `EventState` 枚举成员。
- **转换层** (`events.py`) 错误地将枚举转换为硬编码字符串（如 `"Succeeded"`），并将其定义为 `str` 类型。
- **消费者** (Tests/Subscribers) 因此被迫依赖脆弱的字符串字面量进行断言。

这种不一致导致了测试的脆弱性，任何对状态文本表现形式的微调都会引发大规模的回归错误，且无法通过静态分析工具捕捉，违背了“验证意图而非实现”的工程哲学。

### 用户需求

彻底统一事件状态契约，强制在整个系统中（Spec, Runtime, Tests, E2E）使用类型安全的 `EventState` 枚举作为单一事实来源。

### 评论

这是一个标志性的重构，它实现了“Concord”（和谐）提案的目标。通过消除魔法字符串，我们将系统的状态契约从一个模糊的隐式约定提升为了一个显式的、编译器可验证的物理常数，极大增强了系统的本体论正确性。

### 目标

1.  在 `cascade-spec` 中将 `EventState` 枚举值标准化。
2.  在 `cascade-runtime` 中修正事件类的类型定义和水合（Hydration）逻辑，保持枚举类型的完整性。
3.  在订阅者中实施稳健的枚举比较逻辑。
4.  更新所有受影响的集成测试和 E2E 测试，确保它们遵循新的类型安全契约。

### 基本原理

核心原理是“正本清源”：通过在契约的最底层（Spec 和 Events 定义）确立类型，并迫使所有中间环节（Hydrator）尊重该类型，最终使得消费端（Tests）能够以最稳健、语义化最高的方式执行断言。使用 `StrEnum` 的 `==` 运算符提供了完美的兼容性，既保留了类型安全性，又兼顾了序列化可能引入的微小差异。

### 标签

#intent/refine #flow/ready #priority/high #comp/spec #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/architecture #task/object/event-contracts #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交架构重构

我们将所有修改过的文件添加到暂存区，并创建一个详细的提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/runtime/observability.py
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
packages/cascade-runtime/src/cascade/runtime/services/observability/subscribers.py
packages/cascade-vm/tests/integration/test_context_injection.py
packages/cascade-vm/tests/integration/test_ref_architecture.py
packages/cascade-vm/tests/integration/test_resource_sentry.py
packages/cascade-vm/tests/integration/test_source_node_execution.py
packages/cascade-cli-observer/tests/integration/test_telemetry_contract.py
packages/cascade-spec/tests/unit/test_observability.py
tests/e2e/integration/test_end_to_end.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(events): Unify event state contract to use EventState enum

This commit implements the "Concord" proposal, establishing a strict,
type-safe contract for all event states throughout the Cascade system.

Core Changes:
1. Standardized 'EventState' enum values in 'cascade-spec' to use
   capitalized strings (e.g., 'Succeeded', 'Failed'), aligning the
   Single Source of Truth with real-world representation.
2. Refactored 'TaskExecutionFinished' and 'RunFinished' dataclasses in
   'cascade-runtime' to type the 'status' field as 'EventState' instead of 'str'.
3. Fixed the event hydration logic in 'events.py' to preserve the enum
   type during the transition from IR to rich Event objects.
4. Updated all subscribers and tests (Integration and E2E) to use
   type-safe enum comparisons (e.g., 'event.status == EventState.SUCCEEDED'),
   eradicating all magic string literals.

This refactoring eliminates "semantic drift" and ensures that the system's
state contract is explicit, self-documenting, and protected by static analysis.
~~~~~

### 下一步建议

- **跨语言对齐**: 既然 Python 端的 `EventState` 已经标准化，建议检查 `cascade-vm-rs` (Rust 核心) 中的相关枚举定义，确保它们在跨语言 FFI 边界上也保持一致。
- **状态机审计**: 考虑对系统中的其他核心枚举（如 `ControlCommand` 或 `PortRole`）进行类似的审计，确保没有任何地方仍在使用隐式的字符串约定。
- **文档更新**: 更新架构文档，将“枚举优先契约”作为 Cascade 状态管理的标准最佳实践进行记录。
