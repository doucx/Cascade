好的，阶段 3 的核心转换逻辑已经通过测试验证。现在我们将这些变更作为一个完整的逻辑单元提交。

这标志着 Cascade 3.0 编译系统具备了将抽象逻辑图转换为精密物理拓扑的能力，是迈向“全对称计算物理场”的重要里程碑。

## [COMMIT] feat(compiler): 实现后端 Expander 与 Builder

### 用户需求
完成 Cascade 3.0 编译器后端的核心重构，实现将逻辑节点 (`NodeIR`) 展开为物理三连体并通过拓扑结构连接的能力。

### 评论
这是架构从“解释执行”转向“拓扑驱动”的关键飞跃。通过 `Expander` 实现的微观展开和 `Builder` 实现的宏观布线，我们不仅实现了数据流的物理化，还通过自动插桩实现了零侵入的可观测性。修复 `Fingerprint` 的 Bug 也确保了哈希系统能够正确履行其在 v3.0 规范中的使命。

### 目标
1.  提交 `NodeIR` 和 `GraphIR` 的定义。
2.  提交 `Expander` 及其生成三连体结构的逻辑。
3.  提交 `Builder` 及其处理依赖布线和观测旁路插桩的逻辑。
4.  提交 `Fingerprint` 的验证修复。
5.  提交相关的单元测试。

### 基本原理
通过将逻辑节点“炸开”为微观的三连体，我们将复杂的生命周期管理（漂白、染色、观测）下放到了拓扑结构本身。这使得运行时引擎可以保持极简，完全依赖物理定律（反应堆激发）来驱动执行，从而消除了调度器中的复杂分支判断。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #concept/topology #concept/identity #scope/core #ai/instruct #task/domain/compiler #task/object/backend-engine #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交编译器后端变更

我们将所有涉及 IR 定义、后端实现、修复及测试的文件添加到 Git 暂存区并执行提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ir/models.py
packages/cascade-spec/src/cascade/spec/fingerprint.py
packages/cascade-compiler/src/cascade/compiler/backend/__init__.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/tests/unit/backend/test_expander.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(compiler): Implement Backend Expander and Builder for Triad Expansion

This commit implements the core conversion logic of the Cascade 3.0 compiler backend, enabling the transformation of logical NodeIRs into physical bipartite graph topologies.

Key Features:
1. **NodeIR & GraphIR**: Defined the intermediate representation that serves as the contract between frontend and backend.
2. **Expander**: Implemented the 'Big Bang' logic to expand a single NodeIR into a physical Triad ($F_{pre} \to F_{worker} \to F_{post}$), including the $D_{trace}$ metadata bypass.
3. **Builder**: Implemented the master assembler that wires multiple Triads according to their logical dependencies and automatically instruments start/end observation channels connected to a global $D_{life}$ node.
4. **Fingerprint Fix**: Updated validation logic to support 'canonical' state keys, aligning with the v3.0 hashing axiom.

This provides the physical foundation for fully symmetric observability and decentralized control flow.
~~~~~

### 下一步建议
我们已经完成了编译器的核心构建块。接下来，我们将进入 **阶段 4：控制流与资源 (Advanced Topology)**。

首先我们将处理 **任务 4.1：实现资源背压 ($D_{res}$)**。我们将扩展 `Builder` 的逻辑，使其能够识别任务的资源约束（Constraints），并自动在物理图中创建与全局资源槽位（Resource Slots）的连接，从而通过拓扑结构实现自然的并发控制和限流。
