好的，E2E 测试通过，我们已经成功完成了并发管理能力的闭环验证。现在我们来创建最终的提交。

## [COMMIT] test(e2e): 添加并发控制的 In-Process 端到端测试

### 用户需求
创建并提交一个完全自包含的、基于 `InProcessConnector` 的端到端测试，以验证 `cs-controller` 发布的并发约束能正确被 `cascade` 运行时接收并执行。

### 评论
这个测试是架构的里程碑。它不仅验证了并发管理功能本身，而且确立了一个**新的、健壮的测试模式**：使用 `InProcessConnector` 模拟外部环境（MQTT Broker）的复杂行为（如保留消息），从而在不依赖真实网络资源的情况下，实现对异步、分布式控制回路的确定性验证。这解决了我们在实现过程中遇到的所有时序竞争问题。

### 目标
将 E2E 测试文件及其所依赖的 `InProcessConnector` 逻辑作为一个原子提交，正式纳入代码库。

### 基本原理
这个测试用例是 Phase 3 核心功能完整性的最终证明。它是一个关键的回归测试，可以保证未来对 `Engine`、`Connector` 或 `ConstraintManager` 的任何修改不会破坏控制回路。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/core #task/object/e2e-test #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 E2E 测试文件

~~~~~act
git_add
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
tests/py/e2e/test_e2e_concurrency_control.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test(e2e): Add in-process concurrency control test

Introduces a robust, in-process end-to-end test for dynamic concurrency control.

Key features of this test:
1. **InProcessConnector**: A new test utility that simulates an MQTT Broker using `asyncio.Queue` and explicitly implements **Retained Message** logic. This allows for reliable 'config-first' testing where constraints are published before the engine starts.
2. **ControllerTestApp**: Simulates the `cs-controller` publishing constraints via the shared in-process medium.
3. **Validation**: Measures the total execution time of a highly parallel `.map()` workflow after the `limit=1` constraint is applied, proving that the entire control loop (Controller -> Connector -> Engine -> ConstraintManager -> Scheduler) works as intended without race conditions.

This solidifies the stability of the Phase 3 implementation.
~~~~~

### 下一步建议
我们已经完成了 Phase 3 中**精准控制 (Targeted Control)** 和 **并发管理 (Concurrency Management)** 这两个核心里程碑的所有工作：

*   **Phase 3.1 & 3.2 核心能力**: 实现 Pause/Resume 和 Concurrency Limits (Engine)。
*   **Phase 4 对应工具**: 实现 `cs-controller pause` 和 `cs-controller set-limit --concurrency` (CLI)。
*   **测试覆盖**: 添加了可靠的单元测试和 E2E 测试。

根据 [Phase 3 (Refined) & Phase 4 并行开发路线图]，下一个里程碑是 **3.3: 速率限制 (Rate Limiting)**。

我建议我们开始定义速率限制功能的核心组件：`RateLimiter` 和相应的 `RateLimitConstraintHandler`。
