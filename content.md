简要回答：
图和任务序列化功能已完成并通过测试。我将创建一个 `[COMMIT]` 计划，包含 `serialize.py` 的实现、`__init__.py` 的 API 暴露，以及测试文件的提交。

## [COMMIT] feat(graph): Implement Graph and Node JSON Serialization (to_json/from_json)

### 用户需求
将“图与任务序列化”功能作为一个逻辑完整的单元提交，以支持未来的分布式执行和可视化工具开发。

### 评论
该实现通过将可执行函数对象（`callable_obj`）的引用替换为可序列化的导入路径（`module.qualname`），成功解决了计算图的持久化问题。反序列化过程包含了必要的自适应逻辑，可以解包 `@task` 装饰器产生的 `Task` 实例，确保 `Node` 对象的 `callable_obj` 字段始终恢复为可执行的原始函数，从而保证了运行时的一致性和无损性。这为 Cascade 的分布式和持久化能力奠定了关键基础。

### 目标
创建一个 Git 提交，包含 `src/cascade/graph/serialize.py` 的新增功能、`src/cascade/__init__.py` 的 API 暴露，以及完整的测试用例。

### 基本原理
序列化功能是“阶段四：生态系统与核心工具”中的关键基础设施。将此功能单独提交，有助于隔离变更，并清晰地记录图元数据交换能力在版本历史中的引入。

### 标签
#intent/build #flow/ready #priority/high #comp/core #concept/state #task/domain/core #task/object/serialization #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有相关文件

将序列化模块、API 入口和测试文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/__init__.py
src/cascade/graph/serialize.py
tests/graph/test_serialize.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们执行 `git commit`，附上详细的提交信息。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(graph): Implement Graph and Node JSON Serialization (to_json/from_json)

Introduces serialization utilities for the computation graph and its components, enabling persistent storage and cross-process communication for graph analysis and future distributed execution.

Key features:
- **`cascade.to_json(graph)` / `cascade.from_json(json_str)`**: Top-level API for graph serialization.
- **Function Persistence**: Callable objects (`callable_obj`, `mapping_factory`) are serialized by storing their `module` and `qualname` string paths.
- **Robust Deserialization**: The `from_json` mechanism uses `importlib` to dynamically load functions and includes logic to automatically unwrap `Task` objects, ensuring the Node's callable always holds the raw function reference, maintaining runtime consistency.
- **Component Support**: Serialization includes support for `Param`, `RetryPolicy`, and core graph structure (Nodes, Edges).
~~~~~

### 下一步建议
我们已经完成了图序列化。根据路线图，**任务映射 (`.map`)** 是下一个重要的、尚未实现的阶段三核心功能。我建议我们现在开始实施 `.map()`。
