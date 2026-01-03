好的，所有的测试都已经通过，整个从逻辑编译到物理执行再到事件观测的链路现在已经完全稳固。

我们已经完成了对 **Cascade 3.0** 核心架构的一次重大拨乱反正：
1.  **Probe 归位**：确立了“探测器模型”，消除了编译器对常量的过早优化。
2.  **Pulse 引入**：确立了“分布式脉冲模型”，消除了隐式启动，实现了真正的物理场自洽。
3.  **链路激活**：修复了标准库中的观测信号发射，激活了系统的“全息可观测性”神经系统。

现在，我将生成 `[COMMIT]` 计划，将这些具有里程碑意义的重构固化下来。

## [COMMIT] refactor(core): align with Probe and Distributed Pulse models

### 用户需求
固化近期对编译器、虚拟机及标准库的所有重构成果，确保系统完全符合 Cascade 3.0 物理模型规范。

### 评论
这次重构是 Cascade 3.0 从“有物理外壳的 v2.0”进化为“真正的全对称物理场”的关键跃迁。我们通过牺牲一些早期的、非法的编译时性能，换取了架构的绝对纯粹性和未来的无限优化空间（JIT）。这为后续实现分布式调度、死锁检测和宏节点缓存扫清了所有理论和物理障碍。

### 目标
固化所有相关修改并创建一个详尽的 Git 提交。

### 基本原理
按照 `d3-constraint-quipu-plan-script-rules` 公理，由于本计划涉及 Git 提交操作，因此它不包含任何文件系统修改指令。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/vm #comp/std #concept/physics-model #scope/core #ai/delegate #task/domain/compiler #task/object/physics-alignment #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交架构对齐重构成果

我们将所有涉及的核心包（spec, compiler, std, vm）及其测试文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ports.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): align with Probe and Distributed Pulse models

This commit represents a major architectural realignment of Cascade 3.0, 
shifting from implicit compiler optimizations back to pure physical 
principles as defined in the Genesis Supplement whitepaper.

Key Changes:

1.  **Probe Paradigm for Constants**: 
    The compiler no longer fold constants into DataNode payloads at build 
    time. Every literal input now generates a full physical chain: 
    D_const -> F_probe (const_probe) -> D_probed -> F_bleacher. This 
    restores the "Everything is a sampling action" axiom.

2.  **Distributed Pulse Model**: 
    Removed implicit startup logic. Every source node (zero inputs) is 
    now explicitly wired to a dedicated Pulse node (D_pulse) with 
    initial_tokens=1. This ensures a self-consistent, decentralized, 
    and truly parallel startup flow driven solely by the topology's 
    potential energy.

3.  **Observability Pipeline Activation**: 
    Fixed standard_bleacher and standard_stainer in cascade-std to 
    correctly emit lifecycle events through the 'obs_output' port. 
    Enhanced trace propagation to include logical node IDs and allow 
    workers to augment trace metadata.

4.  **Robust E2E Testing**: 
    Introduced a new event-driven integration test that verifies the 
    entire chain from GraphIR generation to pulse-triggered physical 
    execution, replacing brittle memory-count assertions with stable 
    lifecycle event verification.

These changes ensure that the physical graph is a holographic projection 
of the logical intent, providing full transparency and a solid foundation 
for future JIT optimizations (like macro-node fusion).
~~~~~

### 下一步建议
我们已经夯实了 Cascade 3.0 的物理基础。现在，我们拥有一个真正能够通过物理原语进行自我演化的宇宙。

下一步，我建议我们继续处理 `识别出的过早优化和架构违规.md` 中的最后一项核心违规：**“观测系统的特权路由”**。目前的 `D_life` 拥有 `sys.maxsize` 的无限容量，这虽然避免了观测反压业务，但在物理上是不纯粹的。

我们可以尝试实现一种 **“全息背压 (Holographic Back-pressure)”** 机制：让观测系统的负载能力通过物理通道自然地反压到业务节点，从而实现更真实的系统仿真。如果你准备好了，我们可以开始针对这一点的战略讨论。
