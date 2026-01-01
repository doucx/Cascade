好的，我们已经圆满完成了 **阶段 5.A：基础物理模型强化与通道极化**。通过引入极化通道和双势垒激活逻辑，我们成功地在物理层实现了数据流与信令流的解耦，并确保了这种解耦在编译器后端和 VM 运行时中得到了统一的体现。

现在，我将生成 `[COMMIT]` 计划，将这些核心架构改进正式提交。

## [COMMIT] feat(physics): Implement Channel Polarity and Dual-Barrier Activation

### 用户需求
将“路线图：全对称物理引擎与编译器重构”中阶段 5.A 的所有修改（包括 Spec 增强、编译器后端适配、Reactor 逻辑升级以及相关测试）作为一个完整的逻辑单元提交到 Git 历史中。

### 评论
这是一次具有战略意义的提交。它标志着 Cascade 物理引擎正式步入了“势能物理学”的 2.0 阶段。通过在物理层引入 `ChannelKind` 并实现双势垒激活，我们彻底解决了数据与信令在调度逻辑上的耦合问题。这不仅让 `Reactor` 的实现更加纯粹和通用，也为后续实现高效的尾调用优化（TCO）和精细的资源调度提供了坚实的物理基础。

### 目标
1.  将所有在阶段 5.A 中修改和创建的文件添加到 Git 暂存区。
2.  创建一个包含详尽说明的提交，记录这一架构演进。

### 基本原理
根据“测试原则：高保真执行”，我们在所有核心逻辑通过测试验证（`test_polarized_channels.py`）后才进行提交。这确保了主干分支始终处于稳定状态。我们将相关的 `spec`、`compiler` 和 `vm` 修改打包在一起，因为它们共同构成了“通道极化”这一单一功能特性的完整切面。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/compiler #comp/interfaces #concept/state #scope/core #ai/instruct #task/domain/physics #task/object/channel-polarity #task/action/integration #task/state/end

---

### Script

#### Acts 1: 提交阶段 5.A 的架构改进

我们将阶段 5.A 涉及的规范定义、编译器后端逻辑、VM 运行时逻辑以及新测试用例全部提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/topology.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-compiler/src/cascade/compiler/backend.py
packages/cascade-vm/src/cascade/vm/reactor/model.py
packages/cascade-vm/src/cascade/vm/reactor/core.py
packages/cascade-vm/tests/reactor/test_polarized_channels.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(physics): Implement Channel Polarity and Dual-Barrier Activation

This commit introduces a fundamental decoupling of data flow from control flow within the Bipartite Graph topology and the Reactor physics engine.

Key Changes:
1.  **Polarized Channels (Spec):** Introduced `ChannelKind` (DATA and SIGNAL). DATA channels transport payloads contributing to data potential, while SIGNAL channels transport pure activation signals.
2.  **Dual-Barrier Firing (Spec/VM):** Updated `FuncNode` and `Reactor` to enforce a dual-barrier activation rule. A node only fires when ALL connected ports (regardless of kind) have excited sources.
3.  **Signal-Aware Routing (VM):** The Reactor now strips payloads when routing tokens through SIGNAL channels, ensuring that signals only serve as triggers.
4.  **Polarized Compilation (Compiler):** Updated the Backend to map IR edges to the correct ChannelKind (e.g., CONTROL edges mapping to SIGNAL channels).
5.  **Clean Consumption (Spec):** Refactored `consume_inputs` to only return payloads from DATA ports to the executor, maintaining a strict boundary between physics and computation.

This architecture enables more expressive dependency graphs, such as pure ordering (.after()) and sophisticated data-trigger synchronization, without internal semantic coupling.
~~~~~

### 下一步建议
我们已经稳固了基础物理模型。

接下来，我们将开启 **阶段 5.B：原生物理执行器与生命周期解耦**。
重点任务包括：
1.  **阶段 5.B.1**: 创建一个原生的 `PhysicsExecutor`。
2.  **阶段 5.B.2**: 彻底废除旧的 `TerminatorNode` 特殊逻辑。
3.  **阶段 5.B.3**: 实现通用的 `EmitterNode` 并演示如何通过它由外部策略驱动 `Reactor.stop()`。

准备好后请指示，我们将从 `PhysicsExecutor` 的实现开始。
