简要回答：
测试套件已通过，我将把测试线束的确定性重构和相关的修复工作作为一个完整的工作单元提交。

## [COMMIT] refactor(tests): Consolidate and determinize E2E test harness

### 用户需求
提交通过测试的 E2E 测试线束重构代码，使测试具有确定性并消除对 `asyncio.sleep()` 的依赖。

### 评论
这次重构是核心控制平面稳定性的关键前提。通过将 `InProcessConnector` 和 `ControllerTestApp` 集中到 `harness.py` 中，并确保 `InProcessConnector.subscribe` 在返回前同步处理保留消息，我们消除了 E2E 测试中的所有时序竞态条件。这使得测试更快、更稳定，并为下一步的并发缺陷修复打下了坚实基础。

### 目标
创建一个 Git 提交，包含对 `tests/py/e2e` 目录下所有文件的修改，重点是测试线束的集中化和确定性。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules` 规则，将文件修改和 Git 提交操作分离。本次计划只进行 `git add` 和 `git commit` 操作。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存所有 E2E 测试文件的变更

~~~~~act
git_add
tests/py/e2e/harness.py
tests/py/e2e/test_e2e_concurrency_control.py
tests/py/e2e/test_e2e_control_plane.py
tests/py/e2e/test_e2e_rate_limit_control.py
tests/py/e2e/test_e2e_ttl.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Consolidate and determinize E2E test harness

Consolidates the `InProcessConnector`, `ControllerTestApp`, and utility Executors into `tests/py/e2e/harness.py`.

The core fix is ensuring that `InProcessConnector.subscribe()` synchronously executes callbacks for all matching retained messages before returning. This simulates an instant handshake with the virtual broker, guaranteeing that the `Engine` is fully initialized with all constraints (like `pause` or `limit`) before it begins scheduling tasks.

This change eliminates the need for `asyncio.sleep()` calls in E2E tests, making the test suite faster and 100% deterministic, resolving the issue of time-based test flakiness.
~~~~~

### 下一步建议

我们已经完成了测试线束的确定性重构。根据重构路线图，下一步是进入 **[红灯]** 阶段，编写一个失败的测试来证明 `Engine` 在运行时（而非启动时）无法感知和响应约束变化。

我建议执行 **步骤 2: [红灯] 为运行时控制延迟编写一个失败的测试**，并将其命名为 `test_runtime_pause_interrupts_stage` (如路线图中所述)。这将是第二个 E2E 测试，用于验证 Engine 调度器的响应性缺陷。
