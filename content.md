经过这一系列严密的排查、修复与代码精炼，我们不仅彻底铲除了导致工作流死锁的隐患，还通过引入确定性的异步测试模式，显著提升了 Cascade 测试套件的工业强度。

现在，我们将这些成果正式提交到 `develop` 分支。

## [COMMIT] fix(engine): 增强速率限制解析鲁棒性并修复潜在死锁

### 用户需求
修复控制平面指令解析逻辑中的严重缺陷：当 `cs-controller` 发送格式错误的 `rate` 字符串时，引擎会抛出未捕获的 `ValueError` 并导致关键消息处理任务崩溃，最终引发工作流死锁。

### 评论
这次修复显著增强了 Cascade 的异常屏障。通过在解析层实现容错，我们确保了单个无效指令不会对长活任务的稳定性造成破坏性打击。同时，我们在测试层面的重构（引入 `asyncio.Event` 和利用全局清理 Fixture）标志着我们对异步代码可测试性认知的深化，为后续开发提供了更稳固的脚手架。

### 目标
1.  提交 `RateLimitConstraintHandler` 的健壮性修复代码。
2.  提交经过精炼的 E2E 鲁棒性回归测试用例。
3.  确保 `LocalBusConnector` 恢复到无日志的纯净状态。

### 基本原理
1.  **解析隔离**: 在 `_parse_rate_string` 中封装 `try-except` 块，将底层解析异常转化为高层语义日志，确保消息循环的生命周期不被异常中断。
2.  **确定性验证**: 抛弃脆弱的 `sleep` 猜测，利用 `asyncio.Event` 在 `LocalExecutor` 执行期间制造稳定的观察窗口，从而精确验证引擎在异常后的状态恢复能力。
3.  **遵循 DRY 原则**: 移除测试中重复的清理逻辑，统一依赖 `conftest.py` 提供的全局状态重置服务。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/constraint-manager #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交最终修改

我们将暂存所有经过验证的文件，并执行一次逻辑完整的提交。

~~~~~act
git_add
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
packages/cascade-engine/src/cascade/runtime/constraints/handlers.py
tests/engine/e2e/test_e2e_robustness.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): prevent deadlock on malformed constraint inputs

Fixed a critical bug where malformed 'rate' strings from the control plane
would raise an unhandled ValueError, crashing the constraint update task.
Since this task is responsible for waking up the engine, its crash led
to permanent workflow deadlocks.

Key changes:
1.  **Resilient Parsing**: Wrapped rate parsing in a try-except block.
    Malformed inputs now log a 'constraint.parse.error' and fallback to
    a safe default (1.0) instead of crashing the task.
2.  **Deterministic Test**: Added 'test_e2e_robustness.py' using
    asyncio.Event and real LocalExecutor to reliably verify the fix
    without race conditions.
3.  **Test Hygiene**: Cleaned up redundant cleanup fixtures in favor of
    the global autouse fixture in conftest.py.

This fix significantly improves engine availability and resilience against
invalid control plane telemetry.
~~~~~

### 下一步建议

死锁问题的解决消除了当前最紧迫的稳定性风险。接下来的工作重点可以转向之前用户反馈中提到的**下一阶段基石**：

1.  **增强 `cs-observer`**: 增加对约束变更事件（如 `constraint.parse.error`）的可视化支持，让此类错误能直观地呈现在开发者面前。
2.  **AST 静态分析**: 开始设计基于 AST 的 TCO 静态分析工具，从编译期预防潜在的图构建问题。

你对这个计划满意吗？我们可以随时开始下一步。
