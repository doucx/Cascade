好的，我们已经成功完成了 **Cascade 3.1: 精密端口** 的所有实施阶段。通过引入 `PortDef` 和 `PortRole`，我们彻底消除了物理层最核心的语义模糊性。现在是时候将这一重要的架构里程碑作为一个完整的逻辑单元提交了。

## [COMMIT] feat(core): implement Precision Ports with explicit PortRoles

### 用户需求
完成并提交 "Cascade 3.1: 精密端口" 重构任务的所有变更。

### 评论
这是一次深层次的架构对齐。通过将端口的角色（数据、资源、信号、观测）从运行时的隐式约定转变为编译时的静态真理，我们显著提升了系统的鲁棒性和可测试性。这一变更为未来实现更复杂的控制流（如基于信号的分支和循环）扫清了障碍。

### 目标
将涉及 `cascade-spec`, `cascade-compiler` 和 `cascade-vm` 的所有修改提交到 Git 仓库。

### 基本原理
按照路线图规划，我们已经完成了从规范定义、编译器适配到虚拟机指令强化的全链条重构。由于所有测试已通过且代码已达到 GREEN 状态，现在可以进行原子提交。

### 标签
#intent/build #flow/ready #priority/high 
#comp/spec #comp/compiler #comp/vm #scope/core 
#ai/instruct 
#task/domain/core #task/object/ports #task/action/implementation 
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交精密端口重构的全部代码

我们将把涉及 Spec 定义、编译器生成逻辑、虚拟机执行指令以及所有相关的单元和集成测试的变更添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ports.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/tests/unit/backend/test_expander.py
packages/cascade-compiler/tests/integration/test_observability_congestion.py
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
packages/cascade-vm/src/cascade/vm/instructions/stainer.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/tests/unit/instructions/test_bleacher.py
packages/cascade-vm/tests/unit/instructions/test_stainer.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/integration/test_branching.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): implement Precision Ports with explicit PortRoles

This commit completes the 'Precision Ports' initiative (Cascade 3.1), replacing implicit, string-based port logic with a type-safe, statically defined physics model.

Key Changes:
1. **Spec**: Introduced 'PortRole' (DATA, RESOURCE, SIGNAL, OBSERVABILITY) and 'PortDef' in 'cascade-spec'.
2. **Compiler**: Updated 'Expander' and 'Builder' to explicitly assign roles to all physical ports during graph expansion.
3. **VM**: Refactored 'standard_bleacher' and 'standard_stainer' instructions to derive their behavior directly from the node's 'PortDef' instead of using naming conventions or external filters.
4. **Reactor**: Enhanced the core loop to pass the node instance to instructions, enabling deep inspection of port semantics at runtime.

This architectural shift eliminates a major source of hidden complexity and ambiguity, ensuring that the physical field obeys strict, declaratively defined laws.
~~~~~

### 下一步建议
我们已经稳固了物理层。根据 Cascade 3.0 重构路线图，下一步的宏观任务应当是 **阶段 4：控制流与资源 (Advanced Topology)**。

具体建议：
- **实现 `run_if` 条件执行**: 现在我们有了 `PortRole.SIGNAL`，可以开始实现逻辑：当 Stainer 根据计算结果产生一个带有特定 Tag 的 Signal Token 时，如何通过拓扑结构控制下游节点的激发。
- **物理回环 (Loops)**: 实现基于拓扑结构的重试和循环逻辑。
