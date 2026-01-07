好的，我们现在已经完成了“拓扑化重试”的基础设施建设，包括信息守恒的 `D_context` 通道、核心决策单元 `F_retry` 以及配套的集成测试。现在我们将这些变更打包为一个完整的逻辑提交。

## [COMMIT] feat(core): Implement topological retry infrastructure with D_context and F_retry

### 用户需求
构建 Cascade 物理层重试机制的完整基础设施。这包括解决原始输入信息丢失的架构缺陷（通过 `D_context` 旁路通道），实现标准的重试决策逻辑节点 (`RetryNode` / `standard_retry_logic`)，以及提供相应的集成验证测试。

### 评论
这是一次重要的架构补完。通过将“重试”从一个隐式的运行时策略转化为显式的物理拓扑结构，我们不仅实现了“信息守恒”（确保重试时原始输入可用），还极大地提升了系统在面对故障时的韧性和可观测性。`RetryNode` 的引入标志着 Cascade 向着“万物皆节点”的愿景又迈进了坚实的一步。

### 目标
1.  **信息守恒**: 在 Triad 中引入 `D_context` 通道，持久化任务输入引用。
2.  **决策单元**: 实现 `F_retry` 节点和配套的 `standard_retry_logic` 内核函数。
3.  **类型安全**: 在 `Linker` 中支持基于物理类型的标准库链接。
4.  **质量保证**: 提供完整的集成测试用例，覆盖重试路由和失败路由。

### 基本原理
我们通过在 Triad 微观结构中引入 `D_context` 通道，将任务的“执行上下文”与“观测轨迹”分离。当任务失败时，`Stainer` 会发出错误信号，而 `D_context` 则提供了再次执行所需的“弹药”。`F_retry` 节点作为物理层面的分拣机，根据 Token 中的 `retry_count` 状态做出路由决策。这种设计确保了即便在复杂的重试序列中，物理图的能量流向依然是确定且可追踪的。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/std-library #comp/vm #concept/state #scope/core #ai/delegate #task/domain/core #task/object/retry-infrastructure #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交重试基础设施变更

我们将所有涉及编译器后端、物理规范、标准库实现以及集成测试的文件添加到暂存区并执行提交。

~~~~~act
git_add
packages/cascade-reflection/src/cascade/reflection/naming.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-spec/src/cascade/spec/physical/triad.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-std/src/cascade/std/system/retry.py
packages/cascade-std/src/cascade/std/system/__init__.py
packages/cascade-vm/src/cascade/vm/linker.py
packages/cascade-vm/tests/integration/test_retry_topology.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement topological retry infrastructure with D_context and F_retry

This commit establishes the physical foundation for robust, stateful retries within the Cascade VM, adhering to the principle of "Information Conservation" and "Topological Sovereignty."

Key architectural changes:
1.  **D_context side-channel**: Added a dedicated physical channel in the Triad structure to preserve task input references. This fixes a critical flaw where original inputs were lost upon task failure.
2.  **RetryNode & standard_retry_logic**: Introduced a standard functional node that implements re-routing logic based on retry policies (max_attempts) and token state (retry_count).
3.  **Physical Linker Upgrades**: Enhanced the Linker to support type-based resolution for standard library nodes, moving away from fragile ID-based heuristics.
4.  **Bleacher/Stainer Evolution**: Updated standard Triad ICs to populate and consume the context channel, ensuring a continuous flow of metadata and input refs.

This infrastructure allows the high-level '.with_retry()' DSL to be compiled into a transparent and observable physical topology, rather than hidden imperative code.

Includes comprehensive integration tests in 'test_retry_topology.py' verifying both retry and permanent failure paths.
~~~~~

### 下一步建议
基础设施已经就位。下一步建议：
1.  **编译器策略实现**：开发 `RetryWiringPolicy`，使编译器能够自动将 `LazyResult.with_retry()` 编译为包含 `F_retry` 节点的物理拓扑。
2.  **端到端测试**：编写一个使用 DSL 定义重试的工作流，并验证其在真实运行时的行为。
3.  **退避算法支持**：在 `RetryNode` 中引入 `delay` 和 `backoff` 参数，并实现相应的物理延迟机制。
