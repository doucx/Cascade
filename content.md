太好了。既然测试已经全面通过，这标志着我们成功打通了 Cascade 3.0 VM 模式下的“全息观测链路”。

我们不仅解决了 `run_id` 的溯源问题，还通过“热寂退出”机制解决了物理层并联任务的竞态问题。

## [COMMIT] fix(vm): 确保遥测事件完整性并修复测试桩属性

### 用户需求
将针对 VM 遥测丢失事件、缺失 `run_id` 上下文以及 `cascade-std` 单元测试崩溃的修复方案永久化。

### 评论
这次修复确立了 VM 执行策略的一个核心设计模式：**由业务结果驱动完成，由物理热寂驱动退出。** 这保证了所有的侧链任务（如日志和监控）在主流程结束时都能得到妥善处理。

### 目标
提交针对 `VMExecutionStrategy` 和 `cascade-std` 测试套件的修改。

### 基本原理
按照 TDD 流程，在 RED 状态（捕获错误）到 GREEN 状态（修复并验证）切换后，执行代码入库。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/observability #task/domain/runtime #task/object/vm-strategy #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将修改后的代码和测试文件添加到暂存区，并创建一个详细的提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
packages/cascade-std/tests/unit/triad/test_bleacher.py
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(vm): ensure telemetry completeness and fix mock testing attributes

1. VM Execution Strategy Improvements:
   - Implemented Genesis Injection: Pass the `run_id` into initial tokens via `reactor.prime()`. This ensures all subsequent physics tokens carry the logical context for observability.
   - Refactored Execution Loop: Changed the termination condition to "Run Until Idle". The VM now waits for the reactor to reach a state of zero active tasks and zero new firings after the result future is done. This ensures that observability side-effects (Observer node) have time to drain.

2. Test Suite Fixes:
   - Updated `create_mock_bleach_node` and `create_mock_stain_node` in `cascade-std` to explicitly set the `name` attribute. This fixes the AttributeErrors encountered during heuristic task name extraction.
~~~~~

### 下一步建议
我们现在拥有了一个可观测且稳健的物理执行层。下一步，我建议：
- **性能基准测试**: 运行 `scripts/benchmark_vm_tco.py`，看看增加这些“优雅停机”逻辑后，对物理层的 Step Latency 有何影响。
- **资源限制验证**: 既然 `run_id` 已注入，我们可以开始测试在 VM 模式下，复杂的资源背压（Back-pressure）和并发限制是否如预期般工作。
