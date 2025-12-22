好的，测试通过，这确认了 UDS 信号机制在 Linux/macOS 上的即时唤醒功能以及我们修复的同步机制和 UDS 路径问题。现在是时候将路线图的 **步骤 2** 和 **步骤 4**（性能优化和质量保证）作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划，包含所有相关文件的 `git add` 和 `git commit` 指令。

## [COMMIT] feat(connector): Implement zero-dependency SqliteConnector with UDS signaling

### 用户需求
完成 `SqliteConnector` 的开发和验证，使其在非 Windows 平台上使用 Unix Domain Socket (UDS) 信号机制实现近乎即时的约束更新，同时在 Windows 上优雅地回退到轮询模式。

### 评论
`SqliteConnector` 的实现是 Cascade 走向零外部依赖单机部署的关键里程碑。通过将数据持久化（约束状态）与低延迟通信（UDS）相结合，它提供了一个高性能且易于运维的控制平面后端，可以替代对外部 MQTT Broker 的依赖。本次提交还修复了 UDS 初始化中的底层异步竞争和 API 错误。

### 目标
1.  提交 `SqliteConnector` 的完整实现 (`connector.py`)。
2.  提交用于验证 UDS 信号、轮询回退、TTL 清理和竞争条件修复的所有端到端测试。

### 基本原理
本次提交包含了路线图中的**性能优化**和**质量保证**两个阶段的工作，构成了一个功能完整、经过充分验证且自洽的变更集合。我们修改了 `connector.py` 以支持 UDS/Polling 双模，并重构了测试以使用隔离的 UDS 路径，并最终通过了 UDS 唤醒速度的断言。这个工作单元可以独立提交。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/tests #concept/state #concept/executor #scope/core #scope/dx #ai/delegate #task/domain/storage #task/object/sqlite-connector #task/action/integration #task/state/end

---

### Script

#### Acts 1: 暂存所有已修改的文件

将 `cascade-connector-sqlite` 包中的核心文件和测试文件添加到 Git 暂存区。

~~~~~act
git_add
packages/cascade-connector-sqlite/src/cascade/connectors/sqlite/connector.py
tests/engine/e2e/test_e2e_sqlite_connector.py
~~~~~

#### Acts 2: 执行提交

创建一个描述本次功能和修复的详细提交信息。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(connector): Implement zero-dependency SqliteConnector with UDS signaling

Introduces `SqliteConnector`, a new control plane backend for Cascade that uses SQLite for persistent storage of global constraints.

Key features:
1.  **Zero-Dependency Backend**: Eliminates the mandatory need for an external MQTT broker for single-instance or local deployments.
2.  **Hybrid Signaling**: Utilizes a high-performance Unix Domain Socket (UDS) datagram listener for near-instantaneous constraint updates on Linux/macOS.
3.  **Cross-Platform Fallback**: Automatically reverts to a reliable polling mechanism on Windows environments.

This commit also resolves critical issues identified during testing:
-   **Fix Race Condition**: Corrected the `subscribe` logic to ensure the listener is active *before* the initial state sync, eliminating a window where constraint signals could be lost.
-   **Fix API Misuse**: Explicitly set `family=socket.AF_UNIX` in `create_datagram_endpoint` to correctly bind the UDS path.
-   **Fix Test Harness**: Updated the test fixture to assign unique temporary UDS paths, ensuring parallel test runs do not suffer from resource conflicts.

Validation included e2e tests for concurrency control, TTL expiration, and successful assertion that UDS wakeup time is faster than the polling interval.
~~~~~

### 下一步建议
我们已经完成了 `SqliteConnector` 的核心实现和集成。根据原始路线图，下一步是 **步骤 3: [架构整合] 将新 `Connector` 集成到 CLI 工具中**。

如果你同意，接下来的任务将是：
1.  修改 `cs-controller` (app.py) 和 `cs-observer` (app.py) CLI，引入 `--backend [mqtt|sqlite]` 选项。
2.  在 `cascade.run()` API 门户中支持 `SqliteConnector` 实例注入。

这将允许用户通过命令行和编程接口选择新的后端。
