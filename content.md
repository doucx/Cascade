好的，所有测试都已通过。现在我们将把这次重构作为一个完整的逻辑单元提交，并检查当前的工作区状态。

## [COMMIT] refactor(core): 通过解耦输入契约实现图同构化

### 用户需求
提交所有关于 v1.3 架构重构的变更，该重构旨在将 `Param`/`Env` 定义与图构建解耦，并修复由此引入的 Bug。

### 评论
这是一次关键的架构重构。通过引入 `InputSpec` 和 `WorkflowContext`，我们彻底解决了 `Param` 作为特殊节点带来的概念不一致问题，并极大地提升了 `cs.cli` 的性能和独立性。工作流图现在是完全同构的，所有节点都是 `LazyResult`，这简化了 `Engine` 和 `GraphBuilder` 的核心逻辑，使系统更加健壮和可扩展。

### 目标
1.  将所有与 v1.3 重构相关的、已修改和新增的文件添加到 Git 暂存区。
2.  创建一个清晰、详尽的 Git Commit，记录本次重构的核心思想和收益。
3.  检查提交后工作区的状态，确保没有遗留的未跟踪文件。

### 基本原理
本次重构是一个逻辑上完整的工作单元，它解决了 `Cascade` v1.2 中的核心设计问题，并成功通过了所有测试。现在是将其固化到版本历史中的最佳时机。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/cli #comp/runtime #concept/state #scope/core #scope/api #task/domain/core #task/object/param #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有相关变更

我们将所有已修改和新增的文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/__init__.py
src/cascade/context.py
src/cascade/graph/build.py
src/cascade/internal/__init__.py
src/cascade/internal/inputs.py
src/cascade/runtime/engine.py
src/cascade/runtime/resolvers.py
src/cascade/spec/input.py
src/cascade/spec/task.py
src/cascade/tools/cli.py
tests/graph/test_build.py
tests/graph/test_serialize.py
tests/providers/test_sql.py
tests/runtime/test_flow_manager.py
tests/runtime/test_input_execution.py
tests/spec/test_input_context.py
tests/tools/test_cli.py
~~~~~

#### Acts 2: 提交重构

执行 Git 提交，并附上详细的说明。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Homogenize graph by decoupling input specs

This commit implements the Cascade v1.3 architecture for handling external inputs, moving from special `param` node types to a fully homogeneous graph.

Key Changes:

1.  **Homogeneous Graph**: The special `node_type="param"` has been eliminated. All nodes in the computation graph are now standard `LazyResult` objects, simplifying the `GraphBuilder` and `Engine`.

2.  **Input Specification (`spec.input`)**: Introduced `InputSpec`, `ParamSpec`, and `EnvSpec` dataclasses. These objects hold the metadata (name, default, type, description) for external inputs, separating the *what* from the *how*.

3.  **Workflow Context (`context.py`)**: A new `WorkflowContext` (using `contextvars`) acts as a registry for `InputSpec` objects. This decouples the input contract definition from the graph structure itself.

4.  **Factory Functions (`cs.Param`, `cs.Env`)**: `cs.Param` and the new `cs.Env` are no longer spec objects but factory functions. They perform two roles:
    - Register their corresponding `Spec` object in the `WorkflowContext`.
    - Return a standard `LazyResult` that wraps an internal task (e.g., `_get_param_value`) responsible for fetching the value at runtime.

5.  **Decoupled CLI (`tools.cli`)**: `cs.cli` no longer needs to build the entire computation graph to discover parameters. It now reads directly from the `WorkflowContext`, making CLI generation significantly faster and more robust.

6.  **Bug Fixes**:
    - `ArgumentResolver`: Fixed a bug where it failed to identify internal tasks (`_get_param_value`) because it was comparing a `Task` instance to a raw function. The check is now correctly `node.callable_obj is task.func`.
    - `tools.cli`: Fixed the CLI tool to print the final result of a workflow to stdout.
    - `tests.tools.test_cli`: Resolved a variable scope issue (`NameError`) caused by a local import shadowing the module-level import within a closure.
~~~~~

#### Acts 3: 检查最终状态

检查当前 Git 仓库的状态以确认工作区是干净的。

~~~~~act
git_status
~~~~~

### 下一步建议
我们已经成功完成了 v1.3 的核心重构。现在可以开始处理 `Router` 剪枝的逻辑了，因为我们已经为此奠定了坚实的架构基础。
