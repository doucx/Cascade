这是一个逻辑上完整的、可提交的工作单元。我们将它作为一个特性（Feature）进行提交。

## [COMMIT] feat(connector-sqlite): 实现零依赖的 SqliteConnector 并修复同步逻辑

### 用户需求
根据路线图，实现了 `SqliteConnector` 的第一个版本，作为 `MqttConnector` 的零依赖、高可靠替代方案。

### 评论
本次提交引入了 `SqliteConnector`，它使用 Python 内置的 `sqlite3` 库和 `asyncio.to_thread`，实现了跨平台的约束控制平面。这个实现的关键在于它能够可靠地替代 MQTT 的核心功能：

1.  **模拟保留消息**: 通过在 `subscribe` 时进行一次阻塞式的“初始同步”，确保 `Engine` 在开始调度任务前就接收到所有现有的约束（例如全局暂停）。这解决了启动时的竞争条件。
2.  **检测删除/恢复**: 通过维护内存快照并对比数据库的全量查询结果，Connector 能够可靠地检测到约束的删除（即 `resume` 命令），解决了纯时间戳轮询无法看到删除操作的问题。

所有的核心功能都通过新的 E2E 测试得到验证。

### 目标
创建一个 Git 提交，包含 `SqliteConnector` 的所有文件和配置，以及确保其功能正确的 E2E 测试套件。

### 基本原理
此功能实现了控制平面的关键解耦，是 Cascade 向更轻量化、更易部署的单机/集群模式迈出的重要一步。它将作为后续 Unix Domain Socket 性能优化的稳固基础。本次提交将所有相关文件（包括新的包结构、配置和测试）整合在一起。

### 标签
#intent/build #flow/ready #priority/high #comp/connector-sqlite #comp/tests #comp/build #concept/sync #scope/api #scope/dx #ai/instruct #task/domain/connectors #task/object/sqlite-connector #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加所有新增和修改的文件到暂存区

我们将所有属于 `cascade-connector-sqlite` 包的文件、根 `pyproject.toml` 的变更以及新的测试文件添加到暂存区。

~~~~~act
git_add
packages/cascade-connector-sqlite/src/cascade/__init__.py
packages/cascade-connector-sqlite/src/cascade/connectors/__init__.py
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/__init__.py
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
packages/cascade-connector-sqlite/pyproject.toml
pyproject.toml
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~

#### Acts 2: 创建 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(connector-sqlite): Implement zero-dependency SqliteConnector

Implements the first version of the SqliteConnector, providing a robust, zero-dependency control plane backend using SQLite. This serves as a lightweight alternative to MqttConnector.

Key architectural fixes included:
1.  **Initial Sync**: The connector performs an immediate, blocking data retrieval upon subscription, which correctly simulates MQTT retained messages and eliminates startup race conditions for constraints.
2.  **Diff-Based Polling**: Switched from incremental time-based queries to an in-memory snapshot comparison to reliably detect when constraints are **deleted** (the "resume" command), ensuring the runtime correctly exits a pause state.

This feature is validated via new comprehensive E2E tests for pause, resume, TTL expiration, and idempotent constraint updates.
~~~~~

### 下一步建议
**步骤 2: [性能优化] 增强 Unix Domain Socket (UDS) 信号机制**

既然我们已经完成了功能完备的基线，下一步是消除轮询延迟。在支持的平台上（非 Windows），我们将用 UDS 信号替换 `asyncio.sleep(POLL_INTERVAL)`，实现近乎瞬时的 `Engine` 唤醒。这将是本次开发路线图中的下一个关键步骤。
