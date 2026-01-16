生成 Quipu 计划以执行 Phase 4.1：修复 Builder。

## [WIP] fix(compiler): 修复 Builder 以适配 Dyad SubGraph 模型

### 错误分析
`Builder.build` 方法在填充符号表时，尝试访问 `subgraph.worker` 属性。
```python
AttributeError: 'SubGraph' object has no attribute 'worker'
```
这是因为在 Dyad 重构中，`SubGraph` 的 `worker` 字段已被移除，代码哈希现在存储在 `LauncherNode` 中，且可以通过 `subgraph.launcher` 访问。

### 用户需求
修复 `cascade-compiler` 中的 `Builder` 类，使其能够正确处理 Dyad 架构的 `SubGraph` 对象，从而通过构建过程。

### 评论
这是解决当前测试雪崩式失败的第一步。修复此问题后，编译器将能够生成 `Assembly`，我们将能够继续修复下游的单元测试和集成测试。

### 目标
修改 `packages/cascade-compiler/src/cascade/compiler/backend/builder.py`，将符号表填充逻辑从 `subgraph.worker` 迁移到 `subgraph.launcher`。

### 基本原理
在 Dyad 架构中，`Launcher` 节点持有 `canonical_code_structure_hash`。尽管 `Launcher` 本身是一个内核 IC（标准库组件），但它代表了用户任务的启动点。将 `Launcher` 的 ID 映射到用户代码的哈希值，可以保持 `SymbolTable` 作为“物理节点 -> 逻辑代码”映射表的作用，供测试工具和运行时自省使用。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #task/domain/compiler #task/object/builder #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 Builder 的符号表填充逻辑

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
            # 3.2 Populate Symbol Table from core triad
            if subgraph.worker:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.worker.id] = canonical_hash
~~~~~
~~~~~python.new
            # 3.2 Populate Symbol Table from Dyad
            if subgraph.launcher:
                canonical_hash = node_ir.task.fingerprint[
                    "canonical_code_structure_hash"
                ]
                symbol_table[subgraph.launcher.id] = canonical_hash
~~~~~

### 下一步建议
修复 `Builder` 后，我们需要立即修复 `cascade-compiler` 的单元测试 `test_expander.py`，以验证新的 `Expander` 逻辑生成的拓扑结构是否符合预期。这将为后续修复更复杂的集成测试提供信心。
