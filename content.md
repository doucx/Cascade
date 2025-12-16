Excellent. With all tests passing, the `.map()` feature is now functionally complete and robust. It's time to consolidate this significant architectural upgrade into a single, clean commit.

Here is the `[COMMIT]` plan.

## [COMMIT] feat(core): Implement dynamic task mapping with `.map()`

### 用户需求
将已完成并经过测试的 `.map()` 功能及其相关的架构重构（`LazyFactory` 协议、运行时升级）提交到版本控制中。

### 评论
这是一个里程碑式的提交。通过引入 `factory.map()` API 和底层的 `LazyFactory` 协议，`Cascade` 的核心表达能力得到了质的提升。我们不仅实现了一个强大的动态并行原语，更重要的是，我们为未来构建一个可扩展的 Provider 插件生态系统奠定了坚实的架构基础。`Engine` 的重构也使其更加健壮，能够处理嵌套和递归的图执行，为未来的子工作流等高级功能铺平了道路。

### 目标
创建一个 Git 提交，包含 `.map()` 功能的完整实现，包括协议、数据结构、运行时升级和所有相关的测试用例。

### 基本原理
所有开发和调试工作已经完成，功能形成了一个逻辑上完整且经过充分测试的工作单元。将其作为一个原子提交，可以清晰地记录项目历史，并为后续开发提供一个稳定的基线。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #comp/interfaces #comp/tests #concept/map #scope/api #scope/dx #ai/instruct #task/domain/core #task/object/map-api #task/action/redesign #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 `.map()` 功能及其所有相关变更

我们将所有修改过的文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
src/cascade/graph/build.py
src/cascade/graph/model.py
src/cascade/runtime/engine.py
src/cascade/runtime/protocols.py
src/cascade/spec/task.py
tests/test_map.py
tests/test_stdlib.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement dynamic task mapping with `.map()`

Introduces a powerful `.map()` method on task factories, enabling dynamic, parallel execution of tasks over collections. This is a foundational feature for data processing and dynamic workflows.

Key architectural changes:

1.  **`LazyFactory` Protocol**: A new protocol is defined in `cascade.runtime.protocols` to establish a formal contract for "mappable" entities. This ensures that `.map()` can be universally applied to any task-like object, paving the way for a future plugin ecosystem.

2.  **`Task.map()` API**: The `Task` class now implements the `LazyFactory` protocol, providing a fluent, discoverable `task.map()` API that is superior for developer experience.

3.  **`MappedLazyResult`**: A new spec object is introduced to represent a mapping operation within the computation graph. The `GraphBuilder` is updated to correctly parse this object and build its dependencies.

4.  **Engine Refactoring**: The `Engine` has been significantly refactored to support dynamic, nested graph execution.
    - `Engine.run` now separates resource management from execution.
    - A new `_execute_graph` method allows the engine to recursively execute sub-graphs, which is essential for unfolding `.map()` operations at runtime.
    - `_execute_map_node` handles the fan-out logic, dynamically generating and executing sub-tasks in parallel using `asyncio.gather`.

This implementation successfully decouples the API from the runtime, adheres to the "unified computable value" philosophy, and provides a robust foundation for more advanced dynamic features.
~~~~~

### 下一步建议
我们已经成功地将 `.map()` 集成到了核心中，并验证了其通用性。`LazyFactory` 协议的引入为我们打开了通往一个更广阔生态系统的大门。

**下一步，我强烈建议我们正式启动“阶段四：生态与可扩展性”，其核心是设计并实现 Provider 插件系统。**

一个完美的起点是：将我们刚刚验证过的 `cs.shell` 功能，从标准库中的一个简单 `@task`，**重构为第一个官方的、基于新 Provider 插件模型的 `cascade-shell-provider`**。这将允许我们：
1.  在一个真实且可控的场景中，完善插件发现机制（例如，使用 `entry_points`）。
2.  固化 Provider 必须遵循的接口和最佳实践。
3.  为社区未来贡献自己的 Provider（如 `cs.sql`, `cs.http` 等）提供一个清晰的范例。
