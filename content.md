我们将对资源约束序列化支持的实现进行原子化提交。

## [COMMIT] feat(graph): Serialize and deserialize ResourceConstraint metadata

### 用户需求
确保 `ResourceConstraint` 元数据在计算图序列化（JSON）和反序列化过程中得到保留，支持图的持久化和跨进程传输。

### 评论
资源约束的序列化是实现高级调度器的先决条件，它保证了任务的关键调度信息不会在图生命周期中丢失。这次修改优雅地将 `ResourceConstraint` 结构扁平化为 `requirements` 字典进行存储，并在反序列化时重建对象。

### 目标
创建一个 Git 提交，包含对 `src/cascade/graph/serialize.py` 和 `tests/graph/test_serialize.py` 的所有修改。

### 基本原理
序列化是核心功能的一部分，必须紧跟在模型变更之后完成。这使得 `ResourceConstraint` 功能完整地成为 `Cascade` 的一个稳定特性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/serialization #task/domain/core #task/object/resource-constraint #task/action/serialization #task/state/end

---

### Script

#### Acts 1: 暂存序列化相关的修改

~~~~~act
git_add
src/cascade/graph/serialize.py
tests/graph/test_serialize.py
~~~~~

#### Acts 2: 提交变更

创建一个详细的 Git Commit。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(graph): Serialize and deserialize ResourceConstraint metadata

Updates the graph serialization logic to handle the new `ResourceConstraint` field on the `Node` model.

The `ResourceConstraint` object is serialized into its plain `requirements` dictionary and reconstructed during deserialization. This ensures that resource scheduling metadata is fully preserved when the workflow graph is stored or transmitted.
~~~~~

### 下一步建议
资源约束的核心模型和序列化工作已完成。我们现在可以继续推进下一个核心功能：

**当前状态总结**:
1.  资源约束模型 (`ResourceConstraint`) 及其 API (`.with_constraints()`) 已经完成。
2.  图构建 (`GraphBuilder`) 已经将约束传递给节点 (`Node.constraints`)。
3.  图序列化 (`to_json`/`from_json`) 已经支持约束。

根据开发路线图（`d1-schema-quipu-plan-template` 引用的 `Cascade 库架构与开发规范 v1.3.md`），我们现在已经完成了大部分**阶段四**的工作。

下一个逻辑步骤是：**在运行时利用这些约束，或者继续实现 Provider 插件的完整功能。**

鉴于我们已经实现了 `cs.template` 的基础，我建议我们现在开始设计和实现 **`cs.config` Provider**，它是手册中提到的一个关键组件，用于声明式地从配置中获取值。这将进一步充实我们的 Provider 生态系统。
