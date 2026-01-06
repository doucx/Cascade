太棒了。所有关键测试（包括高压资源竞争测试和背压测试）现已通过，这标志着 Cascade v3.1 的**同步内核 (Sync Kernel)** 和 **引用架构 (Ref-Based Architecture)** 已成功落地。

我们不仅修复了技术上的崩溃，更通过“标量提升”解决了架构上的逻辑矛盾，使系统达到了真正的物理层纯粹性。

## [COMMIT] feat(std,vm): Finalize Sync Kernel and Ref-Based Protocol migration

### 用户需求
将 Cascade 核心执行单元从异步模型迁移到同步物理内核模型，并实施基于引用的数据流协议，确保资源管理和图调度在微秒级延迟下运行。

### 评论
这是一个具有里程碑意义的提交。通过将 `Bleacher`, `Stainer`, `Allocator` 等标准 IC 转换为同步函数，并激活 `Reactor` 的直接调用路径，我们彻底消除了标准操作的线程调度开销。同时，适配后的 `Ref` 协议为未来的分布式扩展和零拷贝数据流奠定了坚实基础。

### 目标
创建一个 Git 提交，包含同步化后的标准库、具备同步路径的反应堆以及适配后的测试套件。

### 基本原理
按照 Cascade v3.1 路线图，我们将“物理层”与“计算层”分离。本提交完成了物理层的“纯净化”：
1.  **物理层同步化**: 反应堆主循环现在可以在单线程内同步、顺序地执行所有控制流逻辑。
2.  **数据权属流转**: 物理令牌现在仅承载 `Ref`，通过标量元数据提升技术，保证了决策的确定性而无需 I/O。

### 标签
#intent/build #flow/ready #priority/critical #comp/std #comp/vm #comp/compiler #concept/ref-architecture #concept/reactor #scope/core #ai/instruct #task/domain/core #task/object/sync-kernel #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交同步内核与引用架构的完整实现

我们将所有修改后的核心组件和测试适配代码提交到版本库。

~~~~~act
git_add
packages/cascade-std/src/cascade/std/probe/const.py
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/src/cascade/std/resource/requestor.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/triad/dispatcher.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(std,vm): Implement Sync Kernel and Ref-Based Protocol

This commit completes Phase 3 of the Ref-Based Architecture (v3.1) by converting all core ICs to a synchronous execution model and introducing Scalar Hoisting for Reference-based data flow.

Key Changes:
1. **Sync Conversion**: Bleacher, Stainer, Dispatcher, and Resource Brokers (Allocator/Reclaimer) are now pure synchronous functions (`def`), allowing the Reactor to execute them without thread-pool or async overhead.
2. **Reactor Activation**: The VM Reactor now detects synchronous functions and executes them directly, significantly reducing step latency and enabling deterministic TCO.
3. **Scalar Hoisting**: Probes now detect scalar values (int, float, bool) and hoist them into Ref metadata. This allows Kernel ICs to perform logic-gate decisions (like resource comparison) without dereferencing from the ObjectStore.
4. **Protocol Alignment**: Standardized the physical function signature to `(inputs, node, resources) -> outputs`.
5. **Test Stabilization**: Updated integration tests and mocks to handle Ref payloads and the new synchronous call stack.

This architecture ensures that the Physics Field remains a low-latency, non-blocking control plane while heavy computation is dispatched to the asynchronous compute plane.
~~~~~

### 下一步建议

1.  **性能基准测试**: 建议运行 `scripts/benchmark_vm_tco.py`，量化同步内核带来的延迟降低。根据设计预期，每步延迟应进入微秒量级。
2.  **分布式存储适配**: 现在 Ref 协议已稳固，可以开始尝试实现基于 `Redis` 或 `Plasma` 的 `ObjectStore` 后端，验证跨进程数据流。
3.  **VM 状态持久化**: 研究如何将基于 Ref 的 `Assembly` 和 `Memory` 状态快照化，以支持工作流的断点续传。
