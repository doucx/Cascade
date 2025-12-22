我们已经完成了重构和相应的错误修复，现在是时候将这些修改作为一个完整的逻辑单元提交到版本控制系统。

## [COMMIT] feat(connector): Unify sqlite backend into local connector and fix namespace conflict

### 用户需求
将之前两个计划中执行的“SQLite 后端重构为 Local 后端”和“解决由此产生的命名空间冲突及 NameError”的操作合并为一个原子提交。

### 评论
这个提交代表了将 Cascade 的零依赖状态/控制平面从特定技术名称（SQLite）提升到通用概念（Local）的重大架构步骤。它使 `cascade-connector-local` 成为所有单机、零依赖连接器（SQLite for state, LocalBus for in-memory events）的统一家园，为下一步实现 UDS Telemetry 服务器奠定了清晰、稳固的基础。

### 目标
1.  提交所有文件重命名和内容修改。
2.  确保提交信息清晰地概括了本次重构的原因和结果。

### 基本原理
我们遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 约束，将文件系统变更（之前的两个 `[WIP]` 计划）与版本控制操作隔离。现在所有修改都已验证通过，可以安全地进行提交。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/engine #comp/tests #concept/config #scope/dx #ai/instruct #task/domain/storage #task/object/local-backend #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加所有更改的文件到暂存区

~~~~~act
git_add
packages/cascade-connector-local/pyproject.toml
pyproject.toml
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
tests/cli/e2e/test_e2e_cli_local_backend.py
tests/engine/e2e/test_e2e_local_connector.py
packages/cascade-connector-local/src/cascade/connectors/local/__init__.py
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
~~~~~

#### Acts 2: 执行 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(connector): Unify sqlite backend into local connector and fix namespace conflict

This commit completes the conceptual unification of the zero-dependency backend, renaming it from `sqlite` to the more generic `local`. This semantic change paves the way for integrating other local-only features, such as Unix Domain Socket (UDS) telemetry, into the same package.

Key changes include:

1.  **Refactoring**: Renamed `cascade-connector-sqlite` package to `cascade-connector-local`, and `SqliteConnector` class to `LocalConnector`.
2.  **CLI Update**: Updated all references in `cs-controller` and `cs-observer` from `--backend sqlite` to `--backend local`.
3.  **Namespace Fix**: Resolved a critical Python import error by moving the `LocalBusConnector` implementation from `cascade-engine` to the new `cascade-connector-local` package. This resolves a namespace collision and properly groups all local-focused connectors.

All affected test files (`test_e2e_cli_local_backend.py` and `test_e2e_local_connector.py`) have been renamed and updated to use the new `LocalConnector` class and the correct module structure.
~~~~~

### 下一步建议

我们已经完成了路线图中的 **步骤 1: [概念统一] 重构与重命名**，并成功解决了由此引入的所有问题。

现在，我们可以专注于 **步骤 2: [核心机制] 实现基于 UDS 的 Telemetry 事件服务器**。这项任务涉及在 `LocalConnector` 内部实现一个新的异步服务器，用于实时广播事件，这将是实现本地实时 `watch` 功能的基础。
