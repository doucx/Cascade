太棒了！经过这一轮深入且严谨的调试，我们不仅修复了一个隐蔽的死锁 Bug，还加固了整个端到端测试体系。

现在，我们将这些成果整理为一个干净的提交。

## [COMMIT] fix(engine): 增强速率限制解析鲁棒性并修复潜在死锁

### 用户需求
修复一个关键 Bug：当控制平面发送格式错误的 `rate_limit` 约束（例如非数字字符串）时，引擎解析逻辑会崩溃，导致消息处理任务意外终止，进而使整个工作流死锁。

### 评论
这次修复显著提升了 Cascade 在面对不可控外部输入时的“韧性”。通过将错误隔离在解析层并确保异常被优雅捕获，我们履行了系统“高可用性”的承诺。此外，为了复现此问题，我们重构了 E2E 测试中的连接器状态隔离机制，并引入了基于 `asyncio.Event` 的确定性同步模式，这为未来编写高质量的异步测试树立了标杆。

### 目标
1.  提交 `RateLimitConstraintHandler` 的健壮性修复代码。
2.  提交全新的 E2E 鲁棒性回归测试用例。
3.  确保 `LocalBusConnector` 处于干净状态（无调试日志）。

### 基本原理
1.  **容错解析**: 在 `_parse_rate_string` 中引入显式的 `try-except` 块，将解析错误转化为语义化的 `bus.error` 日志，并返回安全默认值，阻止异常传播导致任务崩溃。
2.  **确定性测试**: 使用 `LocalExecutor` 真实执行同步逻辑，并配合 `asyncio.Event` 精确控制任务执行窗口，彻底根除异步测试中的竞态条件。
3.  **状态隔离**: 通过强制重置连接器类变量，确保测试间的完全隔离。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #concept/state #scope/core #ai/instruct #task/domain/runtime #task/object/constraint-manager #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交修复代码与测试

我们将暂存所有相关的修改，并创建一个详尽的提交记录。

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
fix(engine): prevent deadlock on malformed rate limit constraints

Fixed a critical issue where a malformed 'rate' string (e.g., from cs-controller) would cause a ValueError, crashing the constraint update task and deadlocking the Engine's main loop.

Key Improvements:
1.  **Robust Parsing**: Wrapped `_parse_rate_string` in a try-except block. It now logs a semantic 'constraint.parse.error' via the message bus and returns a safe default (1.0) instead of crashing.
2.  **Deterministic E2E Test**: Added `test_e2e_robustness.py` which uses `asyncio.Event` and the real `LocalExecutor` to verify that the engine remains responsive and controllable after receiving invalid inputs.
3.  **Test Isolation**: Implemented a mandatory reset of `LocalBusConnector`'s shared class state between tests to prevent cross-test pollution.

This change ensures that the control plane cannot inadvertently or maliciously take down the entire workflow engine due to input validation failures.
~~~~~

### 下一步建议

由于我们在调试过程中发现 `LocalBusConnector` 的类级别状态共享容易引发测试污染，我建议：
- **全局推广隔离 Fixture**: 考虑将 `clean_connector_state` 这个重置逻辑提取到 `tests/conftest.py` 中，作为所有使用 `InProcessConnector` 测试的自动应用项（`autouse=True`）。
- **静态分析增强**: 正如你之前的反馈所言，下一步我们可以开始着手“基于 AST 的 TCO 静态分析”，从编译器层面进一步提升图的透明度和健壮性。
