好的，重命名工作已完成且逻辑清晰。现在我们将这些变更作为一个完整的逻辑单元提交。

## [COMMIT] fix(common): 将错误的 EventBus 命名纠正为 FeedbackBus

### 用户需求

用户确认方案可行，要求将 `cascade-common` 模块中受误导的重命名操作进行修正，将 `EventBus` 改回语义更准确的 `FeedbackBus`。

### 评论

这次提交彻底清除了 `cascade-common` 与 `cascade-engine` 之间的命名冲突。通过区分系统事件（Event）和用户反馈（Feedback），我们恢复了架构的清晰度，这对后续的 TUI 渲染器开发至关重要。

### 目标

1.  将 `cascade-common` 中已修改的文件添加到 Git 暂存区。
2.  创建一个详尽的提交记录，说明此次纠偏的背景和目的。

### 基本原理

遵循 `[COMMIT]` 协议，本计划不包含任何代码修改，仅执行 Git 的版本记录操作。这样可以确保每个提交都是在代码验证通过后进行的，保证了主分支的稳定性。

### 标签

#intent/tooling #flow/ready #priority/high #comp/engine #concept/ui #scope/dx #ai/instruct #task/domain/core #task/object/naming-convention #task/action/correction #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交命名纠偏变更

我将把涉及重命名的核心文件和单元测试文件添加到暂存区，并提交更改。

~~~~~act
git_add
packages/cascade-common/src/cascade/common/messaging/bus.py
packages/cascade-common/src/cascade/common/messaging/__init__.py
packages/cascade-common/tests/unit/test_messaging.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(common): rename incorrectly named EventBus to FeedbackBus

In a previous wide-scoped refactoring, the 'MessageBus' in common.messaging
was accidentally renamed to 'EventBus', causing a semantic collision with
the 'EventBus' used for core engine events.

This commit corrects that mistake by renaming the messaging-specific bus
to 'FeedbackBus'. This name more accurately reflects its role: transporting
user-facing feedback and localized messages, as opposed to the runtime's
EventBus which handles system-level lifecycle and execution events.

Modified files:
- packages/cascade-common/src/cascade/common/messaging/bus.py: Renamed class and instance.
- packages/cascade-common/src/cascade/common/messaging/__init__.py: Updated exports.
- packages/cascade-common/tests/unit/test_messaging.py: Updated unit tests.
~~~~~

### 下一步建议

- **跨包检查**: 建议检查 `cascade-application` 或其他依赖 `cascade-common` 的包，确保它们对 `bus` 的引用仍然正常（由于单例 `bus` 的名称未变，理论上大多数地方应该是透明的，但如果直接引用了 `EventBus` 类型声明，则需要同步更新）。
- **文档更新**: 如果有相关的 API 设计文档，应同步更新类名描述。
