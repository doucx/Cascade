## [WIP] chore: 删除与旧 Blueprint 后端相关的过时测试

### 用户需求
确认 `Backend.compile()` 签名变更导致的 `TypeError` 失败是否符合预期，并决定下一步行动。

### 评论
这是一个积极的信号，表明我们的“焦土式”重构正在按计划进行。删除这些测试是消除技术债务、确保我们完全转向新架构的关键一步。

### 目标
1.  删除 `packages/cascade-compiler/tests/unit/test_backend.py`。
2.  删除 `packages/cascade-compiler/tests/unit/test_backend_enrichment.py`。
3.  删除 `packages/cascade-compiler/tests/unit/test_compiler_linking.py`。

### 基本原理
这些测试文件是为验证旧的、基于 `Blueprint` 和 `ExecutionPlan` 的后端而编写的。随着 `Backend` 被重构为生成 `BipartiteGraph`，这些测试已经失去了它们的验证目标，成为了历史遗留物。我们新创建的 `test_backend_topology.py` 已经取代了它们，成为了 `Backend` 新契约的守护者。

### 标签
#intent/tooling #flow/ready #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/compiler #task/object/backend #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 删除过时的 Backend 测试文件

我们将删除所有与旧 `Blueprint` 生成逻辑相关的测试文件。

~~~~~act
delete_file
packages/cascade-compiler/tests/unit/test_backend.py
~~~~~

~~~~~act
delete_file
packages/cascade-compiler/tests/unit/test_backend_enrichment.py
~~~~~

~~~~~act
delete_file
packages/cascade-compiler/tests/unit/test_compiler_linking.py
~~~~~

### 下一步建议
在完成这次清理之后，我们的代码库将与新的 `Backend` 契约保持一致。

现在，我们可以安全地进入 **阶段 3.3：[TDD] 编译字面量与扇出依赖**。我将为 `test_backend_topology.py` 添加一个新的测试用例，该用例将断言编译器如何正确处理常量输入（字面量）和菱形依赖图，这将使我们的测试再次变红。
