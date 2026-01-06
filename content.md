太棒了。`test_ref_architecture.py` 的通过标志着 Cascade v3.1 "Ref-Based Architecture" 的核心闭环已经彻底打通。我们成功实现了物理控制面（同步/引用）与数据计算面（异步/实体）的完全解耦。

现在，我将生成一个 `[COMMIT]` 计划，将这些里程碑式的变更永久化。

## [COMMIT] feat(vm): 实现 Ref-Based 架构与反应堆进化

### 用户需求
将 v3.1 "Ref-Based Architecture" 的核心实现，包括 Reactor 的 Ingress 处理能力、计算服务集成、标准库 Ref 协议适配以及端到端集成测试，作为一个完整逻辑单元进行提交。

### 评论
这次提交是 Cascade 3.x 演进中的一个转折点。它不仅在技术上实现了同步内核与异步用户态的混合模型，更在工程上验证了“控制即拓扑，数据即引用”的哲学愿景。系统现在的性能潜力已由数据 I/O 限制释放，理论上仅受限于 Python 的循环开销。

### 目标
1.  提交 Reactor 内置处理 Ingress 队列的逻辑。
2.  提交 `const_probe` 的 Ref 协议适配代码。
3.  提交简化的、基于服务模型的 `EventDrivenRunner`。
4.  提交全新的端到端集成测试套件。

### 基本原理
按照路线图的规划，我们已经完成了：
- **物化引用 (Phase 1)**: `Ref` 成为物理图的唯一载荷。
- **出入境模型 (Phase 3)**: `Dispatcher` 发射请求，`ComputeService` 异步执行。
- **反应堆进化 (Phase 4)**: `Reactor` 自主处理 Ingress 周期。
- **集成验证 (Phase 5)**: 通过 E2E 测试确保了整个链条的鲁棒性。

### 标签
#intent/build #flow/ready #priority/critical #comp/vm #comp/std #comp/compiler #concept/executor #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/ref-based-architecture #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交核心架构变更与测试

我们将把受影响的所有包（vm, std, compiler, runtime）的相关修改和新增测试一并提交。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-std/src/cascade/std/probe/const.py
packages/cascade-vm/tests/integration/test_ref_architecture.py
packages/cascade-vm/tests/integration/test_context_injection.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): Finalize v3.1 Ref-Based Architecture and Reactor Evolution

This commit completes the "Entanglement" roadmap (v3.1), fundamentally decoupling the physical control plane from the data plane.

Key Enhancements:
1. Reactor Autonomy: Evolved Reactor.step() to include an 'Ingress Cycle'. The Reactor now internally consumes the ingress_queue, materializing external results into the physical memory, making it a self-contained event-driven state machine.
2. Ref-Based Protocol Adherence: Updated 'const_probe' in std library to materialize literal values into 'Ref' objects before injection into the graph. This ensures that the physical field exclusively flows lightweight references.
3. Disconnected Execution: Integrated 'LocalComputeService' and 'standard_dispatcher' into the core flow. User code execution is now fully delegated to a separate thread pool/service, preventing the Reactor's tick loop from being blocked by I/O or heavy computation.
4. Harness Simplification: Refined 'EventDrivenRunner' to act as a pure component orchestrator, removing redundant manual ingress handling logic.

Testing:
- Added 'test_ref_architecture.py' as a capstone integration test, verifying the full dispatch -> background compute -> ingress -> downstream activation cycle.
- Updated all existing integration and unit tests to comply with the new Ref protocols and service initialization signatures.
~~~~~

### 下一步建议

随着 Ref-Based 架构的稳固，我建议下一步聚焦于以下两个方向：

1.  **确定性 GC 策略 (Phase 6)**：目前 `ObjectStore` 仅支持存储，尚未实现基于拓扑守恒性的垃圾回收。我们需要根据架构报告第 5 节，实现“消费即销毁”或“作用域生命周期”的 GC，以防止内存泄漏。
2.  **JIT 常量折叠优化**：基于 `Purity Over Performance` 原则，我们目前生成了冗余的 `F_probe` 节点来处理常量。现在可以引入一个 JIT 预处理器，在 Reactor 加载图之前，将这些已知的常量 `Ref` 直接注入到 downstream 的 `D_node` 中，从而消除运行时探测开销。

建议从 **GC 策略的 TDD 实现**开始。你意下如何？
