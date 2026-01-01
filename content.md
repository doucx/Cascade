好的，重构工作已经完成并验证通过。现在，我们将这些架构上的改进作为一个完整的逻辑单元提交到仓库。

## [COMMIT] refactor(spec): 统一拓扑规范中的发射器节点定义

### 用户需求
固化对 `cascade-spec` 的重构，将 `PhysicsEmitterNode` 统一到 `PhysicsFuncNode` 中，以消除模式重复并精简拓扑模型。

### 评论
通过这次重构，我们消除了静态拓扑定义中的“概念冗余”。现在的模型更加符合物理直觉：节点只有“函数节点（计算）”和“数据节点（存储）”两类，而“发射器”只是函数节点在具备 `sink_id` 时的特殊表现形式。这不仅简化了代码，也为后续 `Reactor` 和 `Backend` 的实现提供了更清晰的基础。

### 目标
1.  将 `cascade-spec` 中的修改提交到 Git 历史。
2.  确保提交信息清晰地解释了这一架构变动的动机和影响。

### 基本原理
遵循 DRY 原则和全对称架构的本体论，我们通过合并类定义和简化 `BipartiteGraph` 结构，降低了系统的概念复杂性。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #scope/core #ai/instruct #task/domain/architecture #task/object/topology-spec #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交重构代码

我们将修改后的 `topology.py` 文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(spec): unify emitter definition in topology

Eliminated the specialized 'PhysicsEmitterNode' class by merging its 'sink_id' 
property into the base 'PhysicsFuncNode'. Updated 'BipartiteGraph' to remove 
the redundant 'emitter_nodes' map.

This change enforces DRY principles at the schema level and aligns with the 
architectural philosophy that an emitter is simply a function node with a 
defined external sink. This simplifies the static topology model and 
prepares for a more streamlined loading process in the Reactor.
~~~~~

### 下一步建议

我们已经清理了架构中的“碎石”，现在可以正式进入 **5.C** 阶段了。

我建议下一个任务是 **5.C.1：[Compiler] 编译器后端支持信令与生命周期注入**。

在这一步中，我们需要：
1.  修改 `cascade.compiler.backend.Backend`，使其在编译时识别 `EdgeKind.CONTROL` 或新的信令依赖。
2.  实现 `_LifecycleInjector` 逻辑：不再注入 `TerminatorNode`，而是注入一个带有 `sink_id="main_output"` 的 `PhysicsFuncNode`（用于输出结果），并紧接着注入一个带有 `sink_id="__system_lifecycle_signal"` 的 `PhysicsFuncNode`（用于停止 Reactor），它们之间通过 `ChannelKind.SIGNAL` 连接。

如果你准备好了，请指示我开始。
