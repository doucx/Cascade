太棒了。通过引入 `GraphValidator` 和拆分 `Broker` 逻辑，我们不仅解决了死锁和饿死问题，更重要的是，我们将 `Builder` 生成的物理图从“大概正确”提升到了“绝对保真”的高度。

我将生成最终的提交计划。

## [COMMIT] refactor(core): 修复二分图违规并实现基于 IC 的资源协商闭环

### 错误分析

在之前的实现中，系统存在三个核心物理缺陷：
1.  **二分图违规 (Bipartite Violation)**: 编译器在处理任务依赖和资源授权时，直接连接了两个函数节点（如 `Stainer -> Bleacher` 或 `Allocator -> Bleacher`），导致物理场拓扑畸形。
2.  **全输入死锁 (Firing Deadlock)**: 旧的 `Broker IC` 试图在一个节点内处理可选的申请和释放，违反了“全输入激发”原则，导致在没有释放信号时申请操作被无限期阻塞。
3.  **资源饿死 (Resource Starvation)**: 由于 `Reactor` 的线性扫描特性，当 `Allocator` 排在 `Reclaimer` 之前时，持续的请求会抢占 Ledger，导致资源无法归还。

### 用户需求
修复上述物理模型缺陷，确保系统符合 Cascade 3.0 白皮书定义的物理定律，并能正确处理资源竞争。

### 评论
这次重构是“物理层纯粹性优于编译时性能”原则的胜利。我们通过引入静态验证器（Validator）强制实施了物理定律，通过拆分 Allocator/Reclaimer 消除了逻辑歧义，并通过调整拓扑顺序解决了公平性问题。这为后续的 JIT 优化打下了坚实的基础。

### 目标
1.  **建立防线**: 引入 `GraphValidator`，在编译阶段拦截所有违反物理公理的行为。
2.  **重构资源 IC**: 将 Broker 拆分为独立的 `Allocator` 和 `Reclaimer`，实现基于 Ledger 竞争的协商模型。
3.  **修复布线**: 在所有 Func -> Func 的连接处插入中间数据节点，确保严格遵守 F -> D -> F 定律。
4.  **优化调度**: 实施“回收优先”策略，消除活锁风险。

### 基本原理
*   **物理公理化**: 能量（Token）只能存在于库所（Data），转换只能发生在变迁（Func）。
*   **职责分离**: 申请、授权、执行、回收、释放，每一个环节都对应独立的物理实体。
*   **拓扑主权**: 通过图的几何构型（顺序、连接）决定系统的动态行为，而非依赖中心化的调度逻辑。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #comp/vm #concept/topology #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/resource-negotiation #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交核心架构重构

我们将把编译器、标准库以及相关的测试修复作为一个完整的逻辑单元提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ports.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/validator.py
packages/cascade-compiler/src/cascade/compiler/backend/validator.stitcher.yaml
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
packages/cascade-std/src/cascade/std/probe/const.py
packages/cascade-std/src/cascade/std/probe/const.stitcher.yaml
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/src/cascade/std/resource/continuous.py
packages/cascade-std/src/cascade/std/resource/requestor.py
packages/cascade-std/src/cascade/std/resource/requestor.stitcher.yaml
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/tests/unit/resource/test_discrete.py
packages/cascade-std/tests/unit/resource/test_continuous.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): fix bipartite violations and implement IC-based resource negotiation

This is a major architectural correction to align the implementation with the
Cascade 3.0 "Fully Symmetric Computational Physics Field" specification.

Key Changes:
1.  **GraphValidator**: Introduced a static verification phase in the Builder
    to enforce fundamental physical laws, including the Bipartite Rule (F<->D only)
    and Port Connectivity.
2.  **Bipartite Compliance**: Fixed multiple instances where FuncNodes were
    directly connected (e.g., Stainer to Bleacher). Inserted intermediate 
    DataNodes (D_dep, D_seq, D_gnt) to ensure energy conservation laws.
3.  **Broker Decomposition**: Split the monolithic Resource Broker into 
    separate 'Allocator' and 'Reclaimer' ICs. This eliminates 'Optional Input' 
    ambiguity and solves firing deadlocks by transforming resource negotiation 
    into explicit ledger competition.
4.  **Starvation Prevention**: Implemented 'Reclaimer Priority' in the Builder 
    to ensure resources are always returned before new ones are granted, 
    fixing livelock scenarios identified in integration tests.
5.  **Standard Library Enhancements**: Added ConstProbe and Requestor ICs to 
    unify the physical model for parameter sampling and resource tagging.

These changes provide a robust, self-verifying foundation for physical execution 
and full-spectrum observability.
~~~~~

### 下一步建议

1.  **物理启动脉冲 (Pulse Model)**: 虽然现在的任务由输入数据激发，但根据白皮书 4.2 节，我们需要实现全局的启动脉冲机制，以统一驱动所有的探测器节点。
2.  **JIT 优化器启动**: 随着物理图节点数的增加，现在的运行效率已经有所下降。我们可以开始设计 Phase 2 的 JIT Pass，特别是“常量折叠”和“三连体融合”，以抹除这些为了保真而付出的性能抽象税。
3.  **可视化升级**: 强烈建议升级 `cascade-cli` 以支持展示这种复杂的物理图，这对于未来的调试至关重要。
