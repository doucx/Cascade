好的，所有功能实现和集成测试已经完成。我现在将生成一个 `[COMMIT]` 计划来封装这项工作。

## [COMMIT] feat(connector): Integrate SqliteConnector into CLI tools

### 用户需求
将 `SqliteConnector` 作为零依赖的控制平面后端，集成到 `cs-controller` 的 `set-limit/pause/resume` 命令以及 `cs-observer` 的 `status` 命令中，并提供 `--backend [mqtt|sqlite]` 选项。

### 评论
这项工作为 Cascade 提供了关键的单机部署能力，允许用户在不依赖外部服务（如 MQTT broker）的情况下管理工作流约束，极大地增强了工具的实用性和解耦性。我们通过了一系列的测试来验证其在控制平面（写入）和观察平面（读取）上的功能都正确无误。

### 目标
提交所有与 `SqliteConnector` CLI 集成相关的代码和测试文件。

### 基本原理
在功能开发、测试修复和集成测试覆盖都已完成后，现在是一个逻辑上完整的、可交付的工作单元。提交将包括 CLI 逻辑重构、`SqliteConnector` 包导出修复、以及所有新的端到端测试文件。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/connector #comp/tests #scope/api #scope/ux #task/domain/connector #task/object/sqlite-connector #task/action/integration #task/state/end

---

### Script

#### Acts 1: 添加所有更改的文件

~~~~~act
git_add
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/__init__.py
tests/cli-controller/test_controller_app.py
tests/engine/e2e/test_e2e_cli_integration.py
tests/cli/e2e/test_e2e_cli_sqlite_backend.py
~~~~~

#### Acts 2: 执行提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(connector): Integrate SqliteConnector into CLI tools

Integrates the zero-dependency SqliteConnector as an alternative control plane backend for the Cascade CLI utilities.

This allows users to manage runtime constraints (`set-limit`, `pause`, `resume`) and observe current constraints (`status`) without needing an external MQTT broker, by using the `--backend sqlite` option.

Key changes:
- `cs-controller` and `cs-observer` now accept the `--backend [mqtt|sqlite]` flag.
- `cs-observer status --backend sqlite` reads active constraints directly from the local SQLite database.
- Fixed package exports and updated test fixtures to support this multi-backend architecture, ensuring CLI E2E tests pass reliably on both stdout/stderr separation and new backend logic.
~~~~~

### 下一步建议
我们已经完成了 `SqliteConnector` 的集成和测试。根据开发路线图，下一步是 **步骤 5: [最终交付] 撰写用户文档**。

我建议创建一个新的计划来编写相关的用户文档，重点介绍 `SqliteConnector` 的优势、用法以及平台差异。
