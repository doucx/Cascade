好的，焦土政策启动。

我将生成一个计划，彻底删除所有与 v2 实验性 VM 和 Blueprint 编译器相关的代码。这是为 Cascade 3.0 物理模型奠定清晰基础的关键第一步。

## [WIP] refactor: 移除实验性的 VM 和 Blueprint 编译器

### 用户需求
执行“焦土政策”，彻底清空当前与 Cascade v2 实验性 VM 相关的所有实现，为 v3.0 的重构做准备。

### 评论
这是一个至关重要的清理步骤，它将消除路线图中指出的“模型精神分裂”问题。通过删除这些过时且与新架构不兼容的组件，我们确保了 Cascade 3.0 的开发能在一个干净、无歧义的基础上进行，避免了在旧有错误模型上进行修补的诱惑。

### 目标
1.  删除定义 VM 指令集的 `blueprint.py` 文件。
2.  删除 VM 的核心实现 `vm.py`。
3.  删除 `engine.py` 中用于调用 VM 的策略文件 `strategies/vm.py`。
4.  删除将 `LazyResult` 编译为 VM 指令的 `compiler.py` 文件。

### 基本原理
根据《Cascade 3.0 重构路线图》，当前的 VM 和 Blueprint 模型是导致架构矛盾的核心原因。它们代表了与“全对称计算物理场”哲学完全不兼容的命令式、寄存器机模型。因此，必须在开始任何新代码编写之前，将它们彻底从代码库中移除。

### 标签
#intent/refine #flow/ready #priority/critical #comp/spec #comp/engine #comp/graph #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/vm-removal #task/action/cleanup #task/state/begin

---

### Script

#### Acts 1: 焦土政策：删除所有 VM 相关组件

我们将依次删除分布在 `cascade-spec`、`cascade-engine` 和 `cascade-graph` 包中的、构成旧 VM 模型的所有核心文件。

~~~~~act
delete_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/src/cascade/runtime/vm.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~

~~~~~act
delete_file
packages/cascade-graph/src/cascade/graph/compiler.py
~~~~~
