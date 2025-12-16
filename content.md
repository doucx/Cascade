我们已经成功解决了 `cs.Router` 的序列化技术债务，这是支持工作流持久化和分布式执行的关键一步。现在我将生成一个 `[COMMIT]` 计划来提交这些变更。

## [COMMIT] fix(graph): Implement full serialization support for cs.Router

### 用户需求
偿还 Router 序列化的技术债务，确保包含动态路由的工作流能够被无损序列化和反序列化，为分布式执行和持久化工作流打下基础。

### 评论
本次重构通过引入 `routers` 顶级列表和轻量级的 `_StubLazyResult` 代理对象，巧妙地解决了 `Router` 及其内部 `LazyResult` 依赖的循环引用和反序列化问题。这使得 `Cascade` 的 `Graph` 对象现在是完全可序列化的，极大增强了其作为“数据”传递给外部系统的能力。

### 目标
1.  提交 `src/cascade/graph/serialize.py` 中对 Router 序列化逻辑的重写。
2.  提交 `tests/graph/test_serialize.py` 中对测试用例的修复，确保所有 Task 都在模块顶层定义以通过反序列化测试。

### 基本原理
原序列化逻辑无法处理 `Router` 对象的复杂结构。新方法：
1.  将 `Router` 定义从 `Edge` 中提取，集中存储在 JSON 的 `routers` 列表中（规范化）。
2.  使用 `_StubLazyResult` 替代原生的 `LazyResult` 对象作为占位符，在反序列化时连接 `Router` 依赖的节点 ID。
通过这种方式，我们实现了无损的 Round-Trip 序列化，同时解决了 Python 嵌套函数带来的 `AttributeError` 错误。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #concept/state #scope/api #scope/core #ai/instruct #task/domain/core #task/object/serialization #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存并提交变更

将序列化文件和测试文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
src/cascade/graph/serialize.py
tests/graph/test_serialize.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(graph): Implement full serialization support for cs.Router

This commit resolves the critical technical debt where the computation graph's serialization (`to_json`/`from_json`) failed to correctly handle and restore the `cs.Router` object metadata attached to edges.

Key changes:
1.  **Serialization Logic (`serialize.py`):** Routers are now collected and stored in a top-level `routers` list in the JSON output.
2.  **Deserialization Logic (`serialize.py`):** Introduces `_StubLazyResult`, a minimal proxy object containing only the UUID, which is used to reconstruct the `Router` instance during graph loading. This satisfies the runtime requirements of `ArgumentResolver` without needing full LazyResult objects.
3.  **Test Fix:** Nested test functions in `tests/graph/test_serialize.py` were moved to the top level to ensure their callables could be correctly imported via `__qualname__` during deserialization.

This change is fundamental for supporting distributed execution and persistent work flows.
~~~~~

### 下一步建议
我们已经完成了对核心架构的最后一次关键修复。根据战略分析，接下来的重点是增强 **DX (开发者体验)** 和 **Provider 生态**。

我建议的下一步是：**将 `cs.template` 任务提升为更健壮的 Provider**，使其能够处理更复杂的模板场景，并作为后续“预编排”战略（生成 Airflow DAGs/YAMLs）的基石。
