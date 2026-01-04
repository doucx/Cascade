好的，核心重构及其跟进修复已全部完成。现在我将创建一个包含所有变更的 `[COMMIT]` 计划，将这次架构优化的成果正式提交到版本控制系统中。

## [COMMIT] refactor: 重命名运行时的 MessageBus 为 EventBus 以消除命名冲突

### 用户需求

提交所有关于 `MessageBus` 重命名为 `EventBus` 的代码变更，涵盖核心库、SDK、应用程序层以及所有相关的集成和端到端测试。

### 评论

这次重构成功解决了 `cascade-engine` 与 `cascade-common` 之间长期存在的命名冲突（Naming Collision）。通过将运行时的事件分发器明确命名为 `EventBus`，我们清晰地划分了“系统级事件驱动”与“用户级反馈通知”这两个不同的语义领域。这一变更虽然影响面广（涉及多个包和数百个测试引用），但通过自动化的 `sed` 批量处理，我们保证了修改的一致性和完整性。

### 目标

1.  将 `cascade-engine` 中的事件总线类名及模块路径正式提交。
2.  将 `cascade-sdk` 导出的 API 更新记录到 Git。
3.  将受影响的所有测试文件、示例代码和辅助工具的修正内容一并提交。

### 基本原理

遵循 Conventional Commits 规范，我们将此次变更标记为 `refactor`。变更涵盖了文件重命名、类名重命名、API 映射更新以及大规模的文本替换。由于所有包的测试引用已在上一阶段同步修复，目前的 Git 暂存区应该包含一个逻辑上自洽且完整的重构单元。

### 标签

#intent/tooling #flow/ready #priority/medium #comp/engine #comp/sdk #comp/application #scope/api #ai/instruct #task/domain/architecture #task/object/event-bus #task/action/commit #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将添加所有受影响的包目录和测试目录，并执行提交。

~~~~~act
git_add
packages/cascade-engine
packages/cascade-sdk
packages/cascade-application
packages/cascade-library
packages/cascade-graph
packages/cascade-spec
packages/cascade-provider-ipfs
tests
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: rename runtime MessageBus to EventBus

This commit resolves a major naming conflict between 'cascade-engine' and
'cascade-common'. Both packages previously implemented a 'MessageBus' with
entirely different semantics:

1. 'cascade-engine' used it for runtime event dispatching (Pub/Sub).
2. 'cascade-common' uses it for UI/localization feedback (Renderer).

Changes:
- Renamed 'cascade.runtime.bus' to 'cascade.runtime.event_bus'.
- Renamed class 'MessageBus' to 'EventBus' within the engine.
- Updated 'cascade-sdk' imports and public API mappings (cs.EventBus).
- Synchronized 'CascadeApp', 'SubflowProvider', and 'testing' utilities.
- Performed a bulk update of all integration and E2E tests across the monorepo
  to use the new naming convention.

This clarifies the architectural intent: 'EventBus' is the nervous system of
the engine, while 'MessageBus' (in common) is the voice of the system.
~~~~~

### 下一步建议

`EventBus` 的重构已正式完成并提交。现在，系统架构在总线层面已变得清晰。

我建议的下一步动作是：
1.  **启动第二阶段重构**: 对 `cascade-common` 侧的 `MessageBus` 进行重命名（例如改为 `FeedbackBus` 或 `Notifier`）。虽然现在重名问题已解决，但为了极致的语义精确度，将“消息”进一步细化为“反馈”是更有价值的。
2.  **文档更新**: 审查 README.md 或官方架构图，确保它们使用的是 `EventBus` 这一新术语，以保持开发文档与代码实现的一致性。
