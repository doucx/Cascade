好的，我们已经成功构建了 Cascade 的时间基础设施，并通过集成测试验证了其正确性。现在是将这一系列具有里程碑意义的改动作为一个完整逻辑单元进行提交的时候了。

这一改动确立了 Cascade 物理层处理非确定性外部干扰（如时间）的标准范式。

## [COMMIT] feat(vm/std): 实现异步时间延迟架构与 sleep IC

### 用户需求
1.  标准化物理层原子节点的命名与前缀，消除代码中的硬编码字符串。
2.  引入非阻塞的 `ChronosService` 以处理物理层的时间延迟需求。
3.  实现 `std.system.sleep` 内核函数，使物理图具备表达时间维度的能力。

### 评论
这是一个架构级别的增强。通过将“时间”从物理引擎的内部循环中抽离，并将其转化为一种可被消费的“外部脉冲”，我们不仅保持了 Reactor 的同步确定性，还极大地增强了系统的可测试性和可扩展性。这种设计为后续实现“指数退避”等复杂控制策略扫清了障碍。

### 目标
1.  提交物理节点前缀标准 (`NodePrefix`) 及其在编译器、链接器中的应用。
2.  提交 `ChronosService` 及其在 `Machine` 运行时中的集成逻辑。
3.  提交 `standard_sleep` IC 的实现。
4.  提交覆盖生命周期信号、机器集成以及时间服务的全套回归测试。

### 基本原理
我们遵循了“时间即信号”的哲学。物理层通过 `standard_sleep` 发起一个 `DelayRequest`，环境层由 `ChronosService` 负责真实的异步等待。这种“往返”模式确保了 Reactor 永远只需要处理离散的、瞬间的 Token 触发，而无需感知 Wall Clock 的流逝，从而在维持高保真物理模型的同时，兼容了异步现实。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/std #comp/spec #comp/compiler #concept/time #task/domain/physics #task/object/time-architecture #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 Spec 与反射层的规范化修改

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physical/constants.py
packages/cascade-reflection/src/cascade/reflection/naming.py
~~~~~

#### Acts 2: 提交编译器后端的标准化重构

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
~~~~~

#### Acts 3: 提交 VM 核心服务与 ChronosService

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/services/contracts.py
packages/cascade-vm/src/cascade/vm/services/chronos.py
packages/cascade-vm/src/cascade/vm/machine.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~

#### Acts 4: 提交标准库中的 sleep IC

~~~~~act
git_add
packages/cascade-std/src/cascade/std/system/time.py
packages/cascade-std/src/cascade/std/system/__init__.py
~~~~~

#### Acts 5: 提交所有相关的集成测试

~~~~~act
git_add
packages/cascade-vm/tests/integration/test_lifecycle_signals.py
packages/cascade-vm/tests/integration/test_machine_integration.py
packages/cascade-vm/tests/integration/test_time_services.py
~~~~~

#### Acts 6: 创建 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm/std): implement asynchronous time delay architecture and sleep IC

This commit establishes the standard pattern for handling time within the
Cascade physical layer. Key changes include:

1.  Standardized Primitives: Introduced 'NodePrefix' in the spec to eliminate
    hardcoded strings like "const." or "pulse.". All ID generation and
    compiler logic now rely on these safe constants.
2.  ChronosService: Added a dedicated, non-blocking service in the VM
    that handles 'DelayRequest' objects via 'asyncio.sleep'. It reinjects
    tokens into the ingress queue upon completion.
3.  standard_sleep IC: Implemented the physical kernel function that
    bridges the physics layer to the time service.
4.  Infrastructure Integration: Updated 'Machine' to coordinate the
    Reactor, ComputeService, and ChronosService. Updated 'Linker' and
    'Harness' to support the new components.
5.  Robust Testing: Added comprehensive integration tests covering time
    delays, machine lifecycle under drain, and overall architectural
    integrity.

This architecture maintains the synchronous deterministic property of the
Reactor while allowing sophisticated time-based control flow (like backoff
retries) to be implemented as topological patterns.
~~~~~

### 下一步建议
我们现在拥有了完整的时间维度支持。接下来的宏观任务是利用这些组件实现**指数退避（Exponential Backoff）**。

我建议的步骤是：
1.  **架构设计**：确定如何通过 `Builder` 将 `F_retry` 逻辑与 `F_sleep` 节点自动连接起来。
2.  **Kernel 实现**：更新 `standard_retry_logic`，根据 Trace 中的重试计数计算出延迟秒数。
3.  **编译器增强**：修改 `ParameterWiringPolicy` 或创建新的 `RetryWiringPolicy`，在生成物理图时自动织入这些时间节点。

如果你准备好了，我们可以先从讨论 `F_retry` 节点的物理拓扑开始。
