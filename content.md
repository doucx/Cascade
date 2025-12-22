我们已经完成了路线图的第二到第四步：UDS 服务器和客户端的实现，以及由此产生的两个关键 bug 的修复。测试套件现在已完全通过，证明了本地 `watch` 功能的端到端可靠性。

现在是时候将这些重大的功能新增和架构改进作为一个完整的逻辑单元进行提交。

## [COMMIT] feat(connector): Implement UDS Telemetry Server for Local Backend Watch Mode

### 用户需求
将之前所有关于实现 `local` 后端实时 `watch` 功能的开发和修复工作合并为一个原子提交。功能包括：实现 `UdsTelemetryServer`，修改 `LocalConnector` 和 `cs-observer`，并确保 UDS 传输的确定性和稳定性。

### 评论
这个提交代表了 Cascade 可观测性架构的一个关键里程碑。它将实时遥测能力扩展到了零外部依赖的本地部署场景。通过在 `LocalConnector` 中统一 SQLite 状态管理和 UDS 事件广播，我们构建了一个内聚、高效的本地通信骨干。同时，对 UDS 死锁和关机时序竞争的修复，保证了系统在异步环境中的健壮性和优雅退出。

### 目标
1.  提交 UDS 服务器和客户端的所有新增代码。
2.  提交 `LocalConnector` 中新增的 UDS 集成和事件路由逻辑。
3.  提交 `cs-observer` 中新的 `local` 后端支持和用户消息。
4.  提交新的 E2E 测试文件，以确保未来不会引入回归。

### 基本原理
我们遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 约束，在一个独立的 `[COMMIT]` 计划中提交所有已验证的文件系统变更。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/cli #comp/tests #concept/sync #scope/core #scope/ux #ai/instruct #task/domain/storage #task/object/uds-server #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加所有更改和新增的文件到暂存区

~~~~~act
git_add
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
packages/cascade-connector-local/src/cascade/connectors/local/uds_server.py
packages/cascade-cli-observer/pyproject.toml
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
tests/cli/e2e/test_e2e_watch_local_backend.py
~~~~~

#### Acts 2: 执行 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(connector): Implement UDS Telemetry Server for Local Backend Watch Mode

This major feature introduces real-time local observability to Cascade without requiring external dependencies like an MQTT broker.

Key features and fixes:

1.  **UDS Telemetry Server (`UdsTelemetryServer`):** Implemented an asynchronous Unix Domain Socket (UDS) server within the `LocalConnector` package. This server broadcasts real-time telemetry events from the running `Engine`.
2.  **`LocalConnector` Integration:** Modified `LocalConnector` to manage the lifecycle of the UDS server (start on connect, stop on disconnect) and implemented routing logic in `publish()` to direct telemetry events to the UDS server.
3.  **`cs-observer` Client Support:** Updated `cs-observer watch` command with support for `--backend local`, implementing an asynchronous UDS client loop to connect, read, and render JSON Lines events, mirroring the MQTT experience.
4.  **Platform Safety:** Ensured all UDS-related code is guarded by `if sys.platform != "win32"` checks, providing friendly error messages on unsupported platforms.
5.  **Quality Fixes:** Fixed critical bugs including a deadlock in `UdsTelemetryServer.stop()` and a race condition in the E2E test setup by correctly registering `TelemetrySubscriber` with the `Engine` for proper shutdown management.
6.  **E2E Testing:** Added `test_e2e_watch_local_backend.py` to ensure the entire UDS/Telemetry pipeline is robust and deterministic.
~~~~~

### 下一步建议

我们已经完成了路线图中的所有核心步骤。

整个宏观任务：**实现统一的 `local` 后端与实时 `watch` 功能** 现已完成。

接下来，您可以根据您的项目路线图，提供一个新的任务。如果你想继续开发，我建议查看 **用户反馈** 或 **技术债务监测** 中的下一个高优先级项目。
