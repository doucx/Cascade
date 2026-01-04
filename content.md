好的，Phase 4：上下文注入（Context Injection）已经顺利完成并通过了集成测试验证。

我们已经成功建立了“创世注入”与“迹流传播”机制。现在，`run_id` 不再通过全局注册表进行“走私”，而是作为 Token 的内禀属性在物理场中流动，并最终完美地转化为高层业务事件。

## [COMMIT] feat(vm): 实现基于 Trace 的上下文注入机制 (Phase 4)

### 用户需求
在 Cascade 物理场中建立无状态的上下文传播协议，确保 `run_id` 能够从图的入口（Genesis）自动流向每一个遥测节点，而无需依赖全局资源。

### 评论
这是 Cascade 架构演进的一个里程碑。通过将 `run_id` 刻入 `Token.trace`，我们不仅满足了当前的监控需求，还为未来支持 OpenTelemetry 等分布式追踪标准打下了坚实基础。系统现在真正实现了物理层与逻辑层的语义解耦。

### 目标
1.  **Run ID 持久化**: 在 `EventDrivenRunner` 中生成并持有 `run_id`。
2.  **创世注入**: 修改 `Reactor.prime` 和 `Runner.inject_input` 以将 `run_id` 注入到初始 Token 中。
3.  **迹流提取**: 更新 `bleacher` 和 `stainer` 以从 Trace 中提取 `rid` 并填充到 `EventIR` 的 `ctx` 字段。
4.  **全链路验证**: 通过集成测试确保 `EventBus` 产出的领域对象包含正确的 `run_id`。

### 基本原理
根据“创世注入”原则，物理场中的粒子（Token）携带其历史（Trace）。我们将 `run_id` 定义为宇宙的初始微扰，在激发时刻注入系统。由于 `Bleacher` 会自动合并上游 Token 的 Trace，因此 `run_id` 会像染料一样随着数据流自动扩散到图的所有分支，实现了完美的局域性。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/std #comp/engine #concept/observability #task/domain/observability #task/object/context-injection #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交上下文注入功能及测试

我们将更新后的 VM 协议、Harness 逻辑、标准库组件以及新创建的集成测试文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/protocols.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): implement Trace-based context injection (Phase 4)

This commit implements the "Genesis Injection" and "Trace Propagation" patterns,
enabling context awareness (specifically 'run_id') in stateless physics nodes.

Key Changes:
1. Reactor/Harness: Updated prime() and inject_input() to inject a genesis
   trace (containing 'run_id') into tokens at the "moment of creation".
2. Standard Library: Updated standard_bleacher and standard_stainer to
   extract 'rid' from Token.trace and populate EventIR.ctx.rid.
3. Observability: The system now correctly propagates context from raw physical
   traces to rich domain events (e.g., TaskExecutionStarted.run_id).
4. Integration Test: Added test_context_injection.py to verify the full flow 
   from data injection to rich event delivery.

This architecture adheres to the Locality Principle, ensuring that nodes
only act on data they receive, without smuggling context through global resources.
~~~~~

### 下一步建议

随着 Phase 4 的交付，我们的物理场已经具备了完整的生产级可观测性基础。下一步我们将进入 **Phase 5: 清理与验证 (Cleanup & Verification)**。

具体建议：
- **移除 Legacy 代码**: 清理 `VMExecutionStrategy` 和 `Event.from_ir` 中之前为了临时兼容旧 Trace 而留下的硬编码 Hack。
- **E2E 冒烟测试**: 运行 `test_vm_strategy_e2e`，验证从 `LazyResult` 声明到 VM 执行再到控制台日志打印的完整回路是否完全通畅且符合预期。
- **文档更新**: 在 `.stitcher.yaml` 中记录这一新的上下文传播协议。
