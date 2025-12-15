好的，现在我们的底层模型已经稳固，可以为 `Router` 功能创建一个干净的提交了。

## [COMMIT] feat(core): Implement dynamic routing with `cs.Router`

### 用户需求
引入 `cs.Router` 类，允许任务的输入参数根据运行时的 `selector` 值（来自 `Param` 或上游任务），动态地从 `routes` 字典中定义的多个上游任务中选择其结果。

### 评论
`cs.Router` 是 `Cascade` 动态工作流能力的核心组件之一。它将图的连接关系从静态绑定升级为动态选择，极大地增强了库的表达能力。本次实现依赖于 `ParamNode` 的重构，确保了 `Router` 可以与 `Param` 无缝集成，支持多环境配置切换、A/B 测试等高级模式。

### 目标
创建一个 Git 提交，包含 `Router` 的完整实现及其测试用例。

### 基本原理
在 `ParamNode` 重构成功的基础上，`Router` 功能现在是一个逻辑上完整且经过充分测试的工作单元，理应拥有自己独立的提交历史。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/routing #scope/api #ai/instruct #task/domain/core #task/object/router #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 `Router` 功能及其测试

将 `Router` 的规范定义、图构建逻辑修改、执行器处理逻辑以及测试文件添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/__init__.py
src/cascade/adapters/executors/local.py
src/cascade/graph/build.py
src/cascade/graph/model.py
src/cascade/spec/routing.py
tests/test_routing.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(core): Implement dynamic routing with `cs.Router`

Introduces `cascade.Router`, a powerful construct for dynamically selecting a task's input from multiple upstream sources at runtime.

Key changes:
1.  **`spec.routing.Router`:** A new spec class is defined to hold a `selector` (`LazyResult` or `Param`) and a `routes` dictionary.
2.  **`GraphBuilder`:** The builder is enhanced to recognize `Router` objects. It creates a primary edge from the selector to the target node (tagged with the Router instance) and implicit dependency edges from all possible routes to ensure correct execution order.
3.  **`LocalExecutor`:** The executor's argument resolution logic is updated to handle routed edges. It first resolves the selector's value, then uses it to look up the correct upstream result from the routes dictionary and injects it into the task.

This feature enables advanced patterns like multi-environment configuration, A/B testing data sources, and other conditional data flow scenarios.
~~~~~

### 下一步建议
我们已经完成了 `cs.Router` 的实现。根据开发路线图，阶段三的最后一个核心功能是 **任务映射 (`.map`)**。这将是 `Cascade` 支持动态并行和数据处理工作流的关键。我建议我们开始实施 `.map()`。
