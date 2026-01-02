好的，我们已经完成了底层的加固和规范对齐。现在，我们将这些改动作为一个逻辑完整的单元提交，标志着底层物理引擎与编译器后端稳定化阶段的正式结束。

## [COMMIT] refactor(vm): Align node identity spec and unify instruction signatures

### 用户需求
创建一个 Git 提交，包含最近对 `PhysicsNode.id` 规范的修正以及对 `Reactor` 指令签名的统一重构及其相关测试更新。

### 评论
这次提交不仅清除了技术债务（移除了 `Reactor` 中的兼容性回退），还确保了核心规范与实际实现之间的完全一致性。这种概念上的完整性对于 V3.0 重构路线图的后续阶段至关重要，它为接下来的全系统集成提供了一个极其干净和稳固的基础。

### 目标
执行 `git add` 和 `git commit`，永久保存当前的稳定状态。

### 基本原理
我们通过一次性提交这些相互关联的架构改进，维护了提交历史的清晰度。这确保了任何人回顾历史时，都能看到物理引擎接口契约是如何在这一刻达到其最终稳定形式的。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/spec #comp/vm #comp/compiler #scope/dx 
#ai/instruct 
#task/domain/architecture #task/object/core-api #task/action/unification #task/state/end

---

### Script

#### Acts 1: 提交架构稳定化改动

我们将所有受影响的文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-compiler/tests/integration/test_observability_congestion.py
packages/cascade-vm/tests/integration/test_branching.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): align identity spec and unify instruction signatures

This commit finalizes the low-level API contract between the Reactor and its physics instructions.

Key changes:
1.  **Spec Alignment**: Updated 'PhysicsNode.id' docstring to formally adopt path-based identifiers (e.g., 'node_a.bleach') as the primary physical identity, aligning the specification with the superior implementation used in the compiler.
2.  **API Unification**: Removed the legacy 'TypeError' fallback in 'Reactor._fire'. The Reactor now strictly enforces the double-argument '(inputs, node)' signature for all instruction calls, ensuring consistency and predictability.
3.  **Test Hardening**: Updated all integration and unit tests to comply with the new signature contract.

These refinements conclude the stabilization of the physical execution layer, providing a solid foundation for the upcoming full-system integration phase.
~~~~~

### 下一步建议

底层已经完全稳固并已提交。现在我们拥有一个完美的“基准面”。

我建议我们立即启动 **阶段 5: 全系统集成**。我们的第一个里程碑是设计并实现 **`cascade-compiler` 的前端转换器 (Frontend IR Translator)**。

其核心目标是：
1.  实现一个 `IRTranslator` 类。
2.  它能够递归地遍历用户的 `LazyResult` 树（从目标节点开始）。
3.  将这个树解构并“摊平”为 `GraphIR` 格式，包括提取常量、映射依赖关系以及识别资源约束。

这将是打通“用户 DSL”与“物理反应堆”之间鸿沟的最后一块拼图。如果你准备好了，我们可以开始讨论 `IRTranslator` 的具体实现策略。
