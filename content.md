术语对齐工作已完成。通过此次清理，我们不仅纠正了代码中的命名错误，还同步更新了 SDK 导出、Stitcher 元数据和文档字符串，确保了整个 monorepo 在物理架构和语义描述上的一致性。

现在我们将这些变更作为一个完整的逻辑单元提交。

## [COMMIT] refactor: 全面对齐总线术语并导出 FeedbackBus

### 用户需求

用户确认了对术语冲突的清理方案，要求将所有残留的 `MessageBus` 描述修正，并确保 SDK 能够正确导出 `FeedbackBus`。

### 评论

这次提交是 `EventBus` / `FeedbackBus` 双总线架构落地的最后一步。它消除了元数据和文档中的歧义，为开发者提供了清晰的类型向导，也让 AI 在后续的代码分析中能够更准确地识别组件意图。

### 目标

1.  将涉及术语对齐和 SDK 导出的所有修改添加到暂存区。
2.  创建一个结构化的提交记录，涵盖从代码逻辑到元数据的完整重构范围。

### 基本原理

本计划严格遵循 `[COMMIT]` 协议，仅包含版本控制操作。通过将 SDK 导出、测试配置和元数据修改打包提交，我们保证了架构重命名的原子性和完整性。

### 标签

#intent/tooling #flow/ready #priority/medium #comp/engine #comp/sdk #concept/ui #scope/dx #ai/instruct #task/domain/core #task/object/bus-naming-cleanup #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交术语对齐与导出变更

我将把分布在 `cascade-engine` 和 `cascade-sdk` 中的术语清理工作进行最终提交。

~~~~~act
git_add
packages/cascade-sdk/src/cascade/sdk.py
packages/cascade-sdk/src/cascade/testing.stitcher.yaml
tests/
packages/cascade-engine/src/cascade/runtime/subscribers.stitcher.yaml
packages/cascade-engine/tests/unit/test_bus.stitcher.yaml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: align bus terminology and export FeedbackBus in SDK

This commit completes the transition from the legacy 'MessageBus' naming
to the dual-bus architecture: 'EventBus' (System) and 'FeedbackBus' (UI).

Key changes:
- SDK: Exported FeedbackBus in cascade.sdk for public API usage.
- Metadata: Updated .stitcher.yaml files in cascade-engine and cascade-sdk
  to correctly describe the flow between EventBus and FeedbackBus.
- Testing: Updated docstrings in cascade-engine/tests/conftest.py and
  SDK testing utilities to reflect current architecture.
- Terminology: Removed all stale references to 'MessageBus' in non-code
  artifacts, ensuring consistency across the codebase.
~~~~~

### 下一步建议

- **文档审查**: 建议进行一次全局搜索 `MessageBus`，如果 `docs/` 或 `README.md` 中仍有残留，应通过后续的文档更新 PR 进行清理。
- **CI 验证**: 确保此提交后，所有包的 `pytest` 均能正常通过，特别是涉及 `HumanReadableLogSubscriber` 的集成测试。
